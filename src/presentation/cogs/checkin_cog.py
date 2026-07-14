import discord
from discord.ext import commands
from discord import app_commands
from src.infrastructure.planning_center.aio_client import PCOAsyncClient
from src.infrastructure.security.config import config
from src.domain.use_cases.process_checkin import ProcessCheckInUseCase

class CheckInCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Instantiate use cases
        pco_client = PCOAsyncClient(config.pco_app_id, config.pco_secret)
        self.use_case = ProcessCheckInUseCase(pco_client)

    @app_commands.command(name="checkin", description="Check in a person to a Planning Center location.")
    @app_commands.describe(person_id="The PCO ID of the person", location_id="PCO location ID")
    async def checkin(self, interaction: discord.Interaction, person_id: str, location_id: str):
        await interaction.response.defer(ephemeral=True)
        success = await self.use_case.execute_checkin(person_id, location_id)
        if success:
            await interaction.followup.send(f"✅ Successfully checked in person `{person_id}`.")
        else:
            await interaction.followup.send(f"❌ Failed to check in person `{person_id}`.")

    @app_commands.command(name="checkout", description="Check out a person using their Planning Center check-in ID.")
    @app_commands.describe(checkin_id="The PCO Check-in ID")
    async def checkout(self, interaction: discord.Interaction, checkin_id: str):
        await interaction.response.defer(ephemeral=True)
        success = await self.use_case.execute_checkout(checkin_id)
        if success:
            await interaction.followup.send(f"✅ Successfully checked out ID `{checkin_id}`.")
        else:
            await interaction.followup.send(f"❌ Failed to check out ID `{checkin_id}`.")

async def setup(bot):
    await bot.add_cog(CheckInCog(bot))
