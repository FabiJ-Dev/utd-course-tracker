# Starting point of the bot. Just hit the run button to start tracking.

# Essential:
import discord, asyncio, json, os
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
from coursebook import get_sections
from watchlist_store import ( # Multiple imports in one .py are tracked like this.
    get_all_tracked_section_ids,
    get_tracked_query_groups,
    get_users_tracking,
    update_tracked_sections_from_coursebook,
)

# Load environment variables from .env into the process.
load_dotenv()

# Variables from .env that will be used to configure the bot and its behavior.
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_USER_ID = os.getenv("DISCORD_USER_ID")
ERROR_CHANNEL_ID = os.getenv("ERROR_CHANNEL_ID")
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS"))
STATE_FILE = Path("previous_status.json")

# Use this to open the state file to read/write the previous CourseBook status for comparison.
def load_previous_state() -> dict:
    if not STATE_FILE.exists():
        return {}

    with STATE_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)

# Use this to save the new status after each check.
def save_current_state(sections: dict) -> None:
    # The .tmp will be renamed to the actual state file after writing, to avoid corruption.
    temp_file = STATE_FILE.with_suffix(".tmp") 
    with temp_file.open("w", encoding="utf-8") as file:
        json.dump(sections, file, indent=2, sort_keys=True)

    temp_file.replace(STATE_FILE)

# Normalized means lowercasing section IDs and ensuring all expected fields are present for comparison and messaging.
def normalize_sections(sections: dict) -> dict:
    normalized = {}

    for section_id, info in sections.items():
        if not section_id: 
            continue # blank/not found = skip

        normalized_id = section_id.lower()
        fixed_info = dict(info) # Copy the original info to avoid mutating it.
        fixed_info["section_id"] = normalized_id
        normalized[normalized_id] = fixed_info 

    return normalized

# Logic to find which tracked sections have changed from Full to Open since the last check, so we can notify users.
def find_new_openings(previous: dict, current: dict, watched_section_ids: set[str]) -> list[dict]:
    openings = []

    for section_id in sorted(watched_section_ids):
        section_id = section_id.lower() # lowercase the section ID in case of inconsistency or user input errors (such as typing cS or Se)
        if section_id not in current:
            print(f"{section_id} not found in current CourseBook result.")
            continue

        old_status = previous.get(section_id, {}).get("status")
        new_status = current[section_id].get("status")

        print(f"{section_id}: {old_status} → {new_status}")

        if old_status == "Full" and new_status == "Open":
            openings.append(current[section_id])

    return openings


# This prints the DM for a section opening, the main purpose of the bot!
def build_dm_message(info: dict) -> str:
    return (
        "🚨 **Course opened!**\n\n"
        f"**{info.get('section', 'Unknown Section')}** — {info.get('title', '')}\n"
        f"Instructor: **{info.get('instructor', 'TBA')}**\n"
        f"Status: **{info.get('status', 'Unknown')}**\n"
        f"{info.get('url', '')}"
    )


# This prints the message for errors, in case an exception occurs in the bot. Printed to my private error channel.
def build_error_message(error: Exception) -> str:
    return (
        "⚠️ **UTD Course Tracker encountered an error while checking CourseBook.**\n\n"
        f"Error:\n`{error}`\n\n"
        "Possible causes:\n"
        "- CourseBook cookie expired\n"
        "- CourseBook changed its HTML format\n"
        "- CourseBook request timed out\n"
        "- Network/request failure\n\n"
        f"Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
    )


# The Bot class that handles everything.
class ClassBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.bg_task: asyncio.Task | None = None

    async def setup_hook(self):
        await self.load_extension("track")
        await self.load_extension("list")
        await self.load_extension("info")
        test_guild_id = os.getenv("TEST_GUILD_ID")

        if test_guild_id:
            guild = discord.Object(id=int(test_guild_id))
            self.tree.copy_global_to(guild=guild)
            synced_guild_commands = await self.tree.sync(guild=guild)

            self.tree.clear_commands(guild=None)
            synced_global_commands = await self.tree.sync()

            print(f"Synced {len(synced_guild_commands)} commands to test guild {test_guild_id}.")
            print(f"Cleared global commands. Global command count is now {len(synced_global_commands)}.")
        else:
            synced_global_commands = await self.tree.sync()
            print(f"Synced {len(synced_global_commands)} global slash commands.")

        self.bg_task = asyncio.create_task(self.course_check_loop())

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        print(f"Checking CourseBook every {CHECK_INTERVAL_SECONDS} seconds.")

    async def send_error_notification_once(self, error: Exception) -> bool:
        error_message = build_error_message(error)

        if ERROR_CHANNEL_ID:
            try:
                channel = self.get_channel(int(ERROR_CHANNEL_ID))
                if channel is None:
                    channel = await self.fetch_channel(int(ERROR_CHANNEL_ID))

                await channel.send(error_message)
                print(f"Sent error notification to channel {ERROR_CHANNEL_ID}.")
                return True
            except Exception as channel_error:
                print(f"Could not send error message to error channel: {channel_error}")

        if DISCORD_USER_ID:
            try:
                admin_user = await self.fetch_user(int(DISCORD_USER_ID))
                await admin_user.send(error_message)
                print(f"Sent fallback error DM to admin user {DISCORD_USER_ID}.")
                return True
            except Exception as dm_error:
                print(f"Could not send fallback admin error DM: {dm_error}")

        return False

    async def course_check_loop(self):
        await self.wait_until_ready()

        error_alert_sent = False

        while not self.is_closed():
            try:
                previous = load_previous_state()
                print(f"\nChecking CourseBook at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")

                query_groups = get_tracked_query_groups()

                if not query_groups:
                    print("No tracked courses yet.")
                    error_alert_sent = False
                    continue

                current = {}

                for term, subject in sorted(query_groups):
                    sections = await asyncio.to_thread(get_sections, term=term, subjects=(subject,))
                    current.update(normalize_sections(sections))

                changes = update_tracked_sections_from_coursebook(current)

                if changes:
                    print(f"Updated {len(changes)} saved watchlist field(s).")

                    printed_changes = set()

                    for change in changes:
                        change_key = (
                            change["section_id"],
                            change["field"],
                            change["old"],
                            change["new"],
                        )

                        if change_key in printed_changes:
                            continue

                        printed_changes.add(change_key)

                        print(
                            f"  {change['section_id']} "
                            f"{change['field']}: "
                            f"{change['old']} → {change['new']}"
                        )

                watched_section_ids = get_all_tracked_section_ids()

                openings = find_new_openings(
                    previous=previous,
                    current=current,
                    watched_section_ids=watched_section_ids,
                )

                for info in openings:
                    section_id = info["section_id"].lower()
                    message = build_dm_message(info)
                    user_ids = get_users_tracking(section_id)

                    for user_id in user_ids:
                        try:
                            target_user = await self.fetch_user(int(user_id))
                            await target_user.send(message)
                            print(f"Sent opening DM for {info.get('section', section_id)} to user {user_id}")

                        except Exception as dm_error:
                            print(f"Could not DM user {user_id} for {section_id}: {dm_error}")

                save_current_state(current)
                error_alert_sent = False

            except Exception as error:
                print(f"Error while checking CourseBook: {error}")

                if not error_alert_sent:
                    error_alert_sent = await self.send_error_notification_once(error)

            finally:
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)

# The main function to start the bot.
def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN in .env")

    client = ClassBot()
    client.run(DISCORD_TOKEN)
    
# The entry point of the script. When you run this file, it will execute the main() function which starts the bot.
if __name__ == "__main__":
    main()