# Usage: /track CS 3341 26u
# Usage: /untrack CS 3341 26u
# If no section is provided, the command applies to every section of that course.
# If a section is provided, the command only applies to that exact section.

# Imports and helpers
import discord, asyncio, re
from discord import app_commands
from discord.ext import commands

from coursebook import get_sections
from watchlist_store import add_sections_for_user, remove_course_for_user


# Basic input validation for slash command arguments.
COURSE_NUMBER_RE = re.compile(r"^\d{4}$")
TERM_RE = re.compile(r"^\d{2}[a-zA-Z]$")
SECTION_CODE_RE = re.compile(r"^[A-Za-z0-9]+$")


# Normalize section input so users can type "001", ".001", "0W1", etc.
def normalize_section_code(section: str | None) -> str | None:
    if section is None:
        return None

    section = section.strip().lstrip(".").lower()
    return section or None


# Find either all sections of a course, or one exact section if section_code exists.
def find_matching_sections(sections: dict, subject: str, course_number: str, term: str, section_code: str | None = None) -> dict:
    matches = {}

    target_prefix = f"{subject}{course_number}."
    target_suffix = f".{term}"
    specific_section_id = f"{subject}{course_number}.{section_code}.{term}" if section_code else None

    # CourseBook IDs look like: cs3341.0w1.26u or cs4349.001.26f
    for section_id, info in sections.items():
        if not section_id:
            continue

        normalized_id = section_id.lower()

        if specific_section_id:
            is_match = normalized_id == specific_section_id
        else:
            is_match = normalized_id.startswith(target_prefix) and normalized_id.endswith(target_suffix)

        if is_match:
            fixed_info = dict(info)
            fixed_info["section_id"] = normalized_id
            matches[normalized_id] = fixed_info

    return matches


# Format one section for /track and /untrack confirmation messages.
def format_section_for_message(info: dict, include_status: bool = True) -> str:
    section_id = info.get("section_id", "unknown-section")
    status = info.get("status", "Unknown")
    title = info.get("title", "")
    instructor = info.get("instructor") or "TBA"

    if include_status:
        return f"- `{section_id}` — **{status}** — {title}\n  Instructor: **{instructor}**"

    return f"- `{section_id}` — {title}\n  Instructor: **{instructor}**"


# Shared validation for /track and /untrack.
def validate_course_input(subject: str, course_number: str, term: str, section_code: str | None) -> str | None:
    if subject not in {"cs", "se"}:
        return "Only `CS` and `SE` are supported right now."

    if not COURSE_NUMBER_RE.fullmatch(course_number):
        return "Course number must be 4 digits. Example: `/track SE 3341 26u`"

    if not TERM_RE.fullmatch(term):
        return "Term must look like `26u`, `26f`, or `27s`."

    if section_code and not SECTION_CODE_RE.fullmatch(section_code):
        return (
            "Section must be only the section code, like `001`, `0W1`, or `5W1`.\n\n"
            "Do not enter the full CourseBook ID."
        )

    return None


class TrackCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="track", description="Track all sections, or one specific section, of a CS/SE course.")
    @app_commands.describe(
        subject="Course subject: CS or SE",
        course_number="Course number, like 3341 or 4348",
        term="CourseBook term code, like 26u or 26f",
        section="Optional section code, like 001, 0W1, or 5W1. Leave empty to track all sections.",
    )
    @app_commands.choices(subject=[app_commands.Choice(name="CS", value="cs"), app_commands.Choice(name="SE", value="se")])
    async def track(self, interaction: discord.Interaction, subject: str, course_number: str, term: str, section: str | None = None):
        await interaction.response.defer(ephemeral=True, thinking=True)

        subject = subject.lower().strip()
        course_number = course_number.strip()
        term = term.lower().strip()
        section_code = normalize_section_code(section)

        error_message = validate_course_input(subject, course_number, term, section_code)
        if error_message:
            await interaction.followup.send(error_message, ephemeral=True)
            return

        # Fetch fresh CourseBook data so /track saves the latest status and instructor.
        try:
            sections = await asyncio.to_thread(get_sections, term=term, subjects=(subject,))
        except Exception as error:
            await interaction.followup.send(
                "I could not fetch CourseBook.\n\n"
                f"Error: `{error}`\n\n"
                "Your CourseBook cookie may have expired.",
                ephemeral=True,
            )
            return

        matches = find_matching_sections(sections, subject, course_number, term, section_code)

        if not matches:
            target = (
                f"{subject.upper()} {course_number}.{section_code.upper()} in `{term}`"
                if section_code
                else f"{subject.upper()} {course_number} in `{term}`"
            )

            await interaction.followup.send(
                f"I could not find any sections for **{target}**.\n\n"
                "Check that the term code and section code are correct, and that CourseBook has released that schedule.",
                ephemeral=True,
            )
            return

        user_id = str(interaction.user.id)
        added, already_tracked = add_sections_for_user(user_id, matches, subject, course_number, term)

        header = (
            f"✅ Tracking **{subject.upper()} {course_number}.{section_code.upper()}** for `{term}`."
            if section_code
            else f"✅ Tracking **all sections of {subject.upper()} {course_number}** for `{term}`."
        )

        lines = [
            header,
            "",
            f"Added: **{len(added)}** section(s)",
            f"Already tracked: **{len(already_tracked)}** section(s)",
        ]

        if added:
            lines.extend(["", "Newly added sections:"])

            for info in added[:10]:
                lines.append(format_section_for_message(info, include_status=True))

            if len(added) > 10:
                lines.append(f"- and {len(added) - 10} more...")

        # If the user tracks something already saved, show what is already being tracked.
        if already_tracked and not added:
            lines.extend(["", "Already tracked sections:"])

            for info in already_tracked[:10]:
                lines.append(format_section_for_message(info, include_status=True))

            if len(already_tracked) > 10:
                lines.append(f"- and {len(already_tracked) - 10} more...")

        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @app_commands.command(name="untrack", description="Stop tracking all sections, or one specific section, of a CS/SE course.")
    @app_commands.describe(
        subject="Course subject: CS or SE",
        course_number="Course number, like 3341 or 4348",
        term="CourseBook term code, like 26u or 26f",
        section="Optional section code, like 001, 0W1, or 5W1. Leave empty to untrack all sections.",
    )
    @app_commands.choices(subject=[app_commands.Choice(name="CS", value="cs"), app_commands.Choice(name="SE", value="se")])
    async def untrack(self, interaction: discord.Interaction, subject: str, course_number: str, term: str, section: str | None = None):
        await interaction.response.defer(ephemeral=True, thinking=True)

        subject = subject.lower().strip()
        course_number = course_number.strip()
        term = term.lower().strip()
        section_code = normalize_section_code(section)

        error_message = validate_course_input(subject, course_number, term, section_code)
        if error_message:
            await interaction.followup.send(error_message, ephemeral=True)
            return

        user_id = str(interaction.user.id)
        removed = remove_course_for_user(user_id, subject, course_number, term, section=section_code)

        if not removed:
            message = (
                f"You were not tracking **{subject.upper()} {course_number}.{section_code.upper()}** for `{term}`."
                if section_code
                else f"You were not tracking **{subject.upper()} {course_number}** for `{term}`."
            )

            await interaction.followup.send(message, ephemeral=True)
            return

        header = (
            f"🗑️ Stopped tracking **{subject.upper()} {course_number}.{section_code.upper()}** for `{term}`."
            if section_code
            else f"🗑️ Stopped tracking **all sections of {subject.upper()} {course_number}** for `{term}`."
        )

        lines = [header, "", f"Removed: **{len(removed)}** section(s)"]

        for info in removed[:10]:
            lines.append(format_section_for_message(info, include_status=False))

        if len(removed) > 10:
            lines.append(f"- and {len(removed) - 10} more...")

        await interaction.followup.send("\n".join(lines), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TrackCog(bot))