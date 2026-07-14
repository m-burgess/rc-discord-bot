import discord
import logging
import datetime
from discord.ext import commands, tasks
from discord import app_commands
from src.infrastructure.hardware.hardware_manager import HardwareManager
from src.infrastructure.security.config import config
from src.domain.use_cases.trigger_broadcast import TriggerBroadcastUseCase

logger = logging.getLogger(__name__)

class HardwareCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Tie to manager
        self.hw_manager = HardwareManager(
            config.wing_ip,
            config.wing_port,
            config.atem_ip,
            config.blackmagic_camera_ip
        )
        self.use_case = TriggerBroadcastUseCase(self.hw_manager)
        
        # Start background check loop
        self.broadcast_schedule_check.start()

    def cog_unload(self):
        self.broadcast_schedule_check.cancel()

    @tasks.loop(seconds=60.0)
    async def broadcast_schedule_check(self):
        """Background task checking if Sunday service starts to automate broadcast triggers."""
        now = datetime.datetime.now()
        # Check if Sunday, and time is e.g. 09:00:00 AM
        if now.weekday() == 6 and now.hour == 9 and now.minute == 0:
            logger.info("Service scheduled time reached. Automatically triggering broadcast sequence...")
            success = await self.use_case.execute_start_broadcast(wing_snapshot_id=1)
            if success:
                logger.info("Auto broadcast trigger executed successfully.")
            else:
                logger.error("Auto broadcast trigger encountered errors.")

    @broadcast_schedule_check.before_loop
    async def before_broadcast_check(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="recall-snap", description="Manually trigger a Behringer WING snapshot recall.")
    @app_commands.describe(snapshot_id="Numeric index of the WING snapshot to recall")
    async def recall_snap(self, interaction: discord.Interaction, snapshot_id: int):
        await interaction.response.defer(ephemeral=True)
        # Establish connection first
        await self.hw_manager.connect()
        success = await self.hw_manager.recall_wing_snapshot(snapshot_id)
        await self.hw_manager.disconnect()

        if success:
            await interaction.followup.send(f"✅ Successfully recalled Behringer WING Snapshot `{snapshot_id}`.")
        else:
            await interaction.followup.send(f"❌ Failed to recall WING Snapshot `{snapshot_id}`.")

    @app_commands.command(name="start-broadcast", description="Trigger the complete start broadcast orchestration sequence.")
    async def start_broadcast(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        success = await self.use_case.execute_start_broadcast()
        if success:
            await interaction.followup.send("🎥 Broadcast sequence executed. Switcher On Air & Camera Recording!")
        else:
            await interaction.followup.send("⚠️ Broadcast sequence failed or returned partial errors. Check system logs.")

async def setup(bot):
    await bot.add_cog(HardwareCog(bot))
