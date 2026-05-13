# Purpose: Loop to find available class slots in the watchlist
# Only supports 2026SU Software Engineering clubs for now
# Just run this file once, and then it loops forever until stopped or given an error. 

# Essential:
import discord
from dotenv import load_dotenv
import asyncio, json, os
from pathlib import Path
from coursebook import get_sections
from datetime import datetime

# Load environment variables from .env into the process.
load_dotenv()

# Read runtime configuration values from environment variables.
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_USER_ID = os.getenv("DISCORD_USER_ID")
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))

# Path for saving the last known state of watched sections.
STATE_FILE = Path("previous_status.json")

WATCHLIST = {
    "se2340.0u1.26u",
    "se3341.0u1.26u",
    "se3341.0u2.26u",
    "se3341.0w1.26u",
    "se3345.0u1.26u",
    "se3345.5w1.26u",
    "se3354.0w1.26u",
    "se3354.5w1.26u",
    "se3377.0w1.26u",
    "se4347.0u1.26u",
    "se4347.5u1.26u",
    "se4348.0u1.26u",
    "se4348.5u1.26u",
    "se4352.0u1.26u",
    "se4376.0u1.26u",
    "se4381.0w1.26u",
    "se6329.0w1.26u",
    "se6367.0u1.26u",
    "se6387.0w1.26u",
}

# Start with the previous state from the disk. Use "r" for read.
def load_previous_state() -> dict:
    if not STATE_FILE.exists():
        # When there is no saved state yet, start with an empty record.
        return {}

    with open(STATE_FILE, "r") as file:
        return json.load(file)


# The new state of the class will get sent to disk. Use "w" for write.
def save_current_state(sections: dict) -> None:
    with open(STATE_FILE, "w") as file:
        json.dump(sections, file, indent=2)


# Key of the bot - find_new_openings will detect changes in Coursebook for open classes.
def find_new_openings(previous: dict, current: dict) -> list[dict]:
    openings = []

    # sorted(WATCHLIST) sorts the classes in the SE track to numbered order.
    for section_id in sorted(WATCHLIST):
        if section_id not in current:
            print(f"{section_id} not found in current CourseBook result.")
            continue

        old_status = previous.get(section_id, {}).get("status")
        new_status = current[section_id]["status"]
        print(f"{section_id}: {old_status} → {new_status}")

        # Only treat Full → Open as a new opening.
        if old_status == "Full" and new_status == "Open":
            openings.append(current[section_id])

    # Following this, send the data to build the DM message.
    return openings

def build_dm_message(info: dict) -> str:
    return (
        "🚨 **Course opened!**\n\n"
        f"**{info['section']}** — {info['title']}\n"
        f"Status: **{info['status']}**\n"
        f"{info['url']}"
    )

# Bot loop - use asyncio to sleep during the required period to not spam Coursebook with requests.
class ClassBot(discord.Client):
    async def setup_hook(self):
        # Create a background task (bg_task) before the bot starts processing events.
        self.bg_task = asyncio.create_task(self.course_check_loop())

    async def on_ready(self):
        # Called once when the bot has successfully connected.
        print(f"Logged in as {self.user}")
        print(f"Checking CourseBook every {CHECK_INTERVAL_SECONDS} seconds.")

    async def course_check_loop(self):
        await self.wait_until_ready()

        if not DISCORD_USER_ID:
            raise RuntimeError("Missing DISCORD_USER_ID in .env")

        # Fetch the target user once so we can send DMs repeatedly.
        user = await self.fetch_user(int(DISCORD_USER_ID))
        error_dm_sent = False

        while not self.is_closed():
            try:
                previous = load_previous_state()

                # All checks timestamped for debugging and validation.
                print(f"\nChecking CourseBook at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
                current = await asyncio.to_thread(get_sections)

                openings = find_new_openings(previous, current)

                for info in openings:
                    message = build_dm_message(info)
                    await user.send(message)
                    print(f"Sent DM for {info['section']}")

                save_current_state(current)

                # If everything succeeded, allow future error notifications again.
                error_dm_sent = False

            except Exception as error:
                print(f"Error while checking CourseBook: {error}")

                if not error_dm_sent:
                    try:
                        await user.send(
                            "⚠️ ClassBot encountered an error while checking CourseBook:\n"
                            f"`{error}`\n\n"
                            "The CourseBook cookie may have expired."
                        )
                        error_dm_sent = True
                    except Exception as dm_error:
                        print(f"Could not send error DM: {dm_error}")

            finally:
                # Wait the configured amount of time before checking again.
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN in .env")

    intents = discord.Intents.default()
    client = ClassBot(intents=intents)
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()