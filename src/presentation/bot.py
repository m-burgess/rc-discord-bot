import discord
import logging
import traceback
from discord.ext import commands
from discord import app_commands
from src.infrastructure.security.config import config
from src.infrastructure.storage.state_manager import SQLiteStateManager
from src.infrastructure.storage.logger import setup_logger, DatabaseLogger

# Configure system logger
setup_logger()
logger = logging.getLogger(__name__)

# Initialize database components
db_manager = SQLiteStateManager()
db_logger = DatabaseLogger(db_manager)

class RCTree(app_commands.CommandTree):
    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """Global error catcher for slash commands to log tracebacks to SQLite."""
        command_name = interaction.command.name if interaction.command else "Unknown"
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id) if interaction.guild else "DM"
        
        # Format traceback
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        db_logger.log_command_error(command_name, user_id, guild_id, tb)

        # Notify the user privately
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"⚠️ An error occurred while executing `/ {command_name}`. The issue has been logged.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"⚠️ An error occurred while executing `/ {command_name}`. The issue has been logged.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Failed to send error notification message to user: {e}")

class RCBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            tree_cls=RCTree
        )
        self.db = db_manager
        self.db_logger = db_logger

    async def setup_hook(self) -> None:
        # Load Cogs
        cogs = [
            "src.presentation.cogs.checkin_cog",
            "src.presentation.cogs.service_cog",
            "src.presentation.cogs.roster_cog",
            "src.presentation.cogs.event_cog",
            "src.presentation.cogs.hardware_cog"
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded extension: {cog}")
            except Exception as e:
                logger.exception(f"Failed to load extension {cog}: {e}")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        # Sync slash commands with Discord
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} application command(s) globally.")
        except Exception as e:
            logger.error(f"Failed to sync command tree: {e}")

# Helper to run the bot
def main():
    if not config.discord_token or config.discord_token == "MOCK_DISCORD_TOKEN":
        logger.warning("No valid DISCORD_TOKEN is set in the environment. Running in mock/dry-run mode is advised.")
    bot = RCBot()
    # In a real environment, you'd call bot.run(config.discord_token)
    return bot

if __name__ == "__main__":
    main()
