import asyncio
import re

import discord
from discord import app_commands
from discord.ext import commands

from coursebook import get_sections


COURSE_NUMBER_RE = re.compile(r"^\d{4}$")
TERM_RE = re.compile(r"^\d{2}[a-zA-Z]$")
SECTION_CODE_RE = re.compile(r"^[A-Za-z0-9]+$")


def normalize_section_code(section: str | None) -> str | None:
    if section is None:
        return None

    section = section.strip().lstrip(".").lower()
    return section or None


def find_matching_sections(
    sections: dict,
    subject: str,
    course_number: str,
    term: str,
    section_code: str | None = None,
) -> dict:
    matches = {}

    target_prefix = f"{subject}{course_number}."
    target_suffix = f".{term}"
    specific_section_id = f"{subject}{course_number}.{section_code}.{term}" if section_code else None

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


def format_section_info(info: dict) -> str:
    return (
        f"`{info.get('section_id', 'unknown-section')}` — **{info.get('status', 'Unknown')}**\n"
        f"{info.get('title', '')}\n"
        f"Instructor: **{info.get('instructor', 'TBA')}**\n"
    )


class InfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="info",
        description="Show live CourseBook info for a CS/SE course or specific section.",
    )
    @app_commands.describe(
        subject="Course subject: CS or SE",
        course_number="Course number, like 3341 or 4349",
        term="CourseBook term code, like 26u or 26f",
        section="Optional section code, like 001, 0W1, or HON.",
    )
    @app_commands.choices(
        subject=[
            app_commands.Choice(name="CS", value="cs"),
            app_commands.Choice(name="SE", value="se"),
        ]
    )
    async def info(
        self,
        interaction: discord.Interaction,
        subject: str,
        course_number: str,
        term: str,
        section: str | None = None,
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)

        subject = subject.lower().strip()
        course_number = course_number.strip()
        term = term.lower().strip()
        section_code = normalize_section_code(section)

        if subject not in {"cs", "se"}:
            await interaction.followup.send("Only `CS` and `SE` are supported right now.", ephemeral=True)
            return

        if not COURSE_NUMBER_RE.fullmatch(course_number):
            await interaction.followup.send("Course number must be 4 digits. Example: `/info CS 3341 26u`", ephemeral=True)
            return

        if not TERM_RE.fullmatch(term):
            await interaction.followup.send("Term must look like `26u`, `26f`, or `27s`.", ephemeral=True)
            return

        if section_code and not SECTION_CODE_RE.fullmatch(section_code):
            await interaction.followup.send("Section must be only the section code, like `001`, `0W1`, or `HON`.", ephemeral=True)
            return

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
            await interaction.followup.send("No matching sections found.", ephemeral=True)
            return

        header = (
            f"ℹ️ **CourseBook info for {subject.upper()} {course_number}.{section_code.upper()} `{term}`:**"
            if section_code
            else f"ℹ️ **CourseBook info for {subject.upper()} {course_number} `{term}`:**"
        )

        lines = [header, ""]

        for info in matches.values():
            lines.append(format_section_info(info))
            lines.append("")

        message = "\n".join(lines)

        if len(message) > 1900:
            message = message[:1900] + "\n\n...too many sections. Try using a specific section code."

        await interaction.followup.send(message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(InfoCog(bot))