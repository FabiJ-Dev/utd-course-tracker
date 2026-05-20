# Usage: /list (no arguments)
# Prints the list of courses a user is currently tracking. 

# Essential:
import discord
from discord import app_commands
from discord.ext import commands
from watchlist_store import load_watchlist

class ListCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="list", description="Show the classes you are currently tracking.")
    async def list_watchlist(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        user_id = str(interaction.user.id)
        data = load_watchlist()
        user_data = data.get("users", {}).get(user_id, {})
        sections = user_data.get("sections", {})
        if not sections:
            await interaction.followup.send("You are not tracking any classes yet.", ephemeral=True)
            return

        lines = ["📋 **Your tracked classes:**", ""]

        for section_id, info in sorted(sections.items()):
            title = info.get("title", "")
            status = info.get("status", "Unknown")
            instructor = info.get("instructor", "TBA")
            url = info.get("url", "")
            lines.append(
                f"`{section_id}` — **{status}** — {title}\n"
                f"Instructor: **{instructor}**\n"
            )

        message = "\n".join(lines)

        # Edge case that I need to work on later: If the user is tracking a lot of classes, the message might exceed Discord's character limit. For now, I'll just truncate it and add a note.
        if len(message) > 1900:
            message = message[:1900] + "\n\n...list too long. Add pagination later."

        await interaction.followup.send(message, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ListCog(bot))