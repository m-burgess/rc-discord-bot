import discord
from discord.ext import commands
from discord import app_commands
from src.infrastructure.google_workspace.apps_script import GoogleAppsScriptHelper

class EventCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.apps_script = GoogleAppsScriptHelper()

    @app_commands.command(name="create-event", description="Establish a new calendar event placeholder.")
    @app_commands.describe(name="Event Name", date="Event Date (YYYY-MM-DD)")
    async def create_event(self, interaction: discord.Interaction, name: str, date: str):
        # Business logic can be added/expanded here
        await interaction.response.send_message(
            f"📅 **Event Created!**\n- **Name:** {name}\n- **Date:** {date}",
            ephemeral=False
        )

    @app_commands.command(name="guest-registration", description="Get a pre-filled Google Form link to register guest details.")
    async def guest_registration(self, interaction: discord.Interaction):
        discord_id = str(interaction.user.id)
        username = interaction.user.name
        
        # Generate link prefilled with discord credentials
        link = self.apps_script.generate_prefilled_link(discord_id, username)
        
        embed = discord.Embed(
            title="Guest Registration Form",
            description="Please fill out this form to complete your registration. Your Discord ID has been pre-filled to link your account.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Registration Link", value=f"[Click Here to Register]({link})")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(EventCog(bot))
