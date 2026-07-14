import discord
from discord.ext import commands
from discord import app_commands
from src.domain.use_cases.calculate_counts import CalculateCountsUseCase
from src.infrastructure.storage.state_manager import SQLiteStateManager

class CountView(discord.ui.View):
    def __init__(self, use_case: CalculateCountsUseCase):
        super().__init__(timeout=None) # Persistent view
        self.use_case = use_case

    @discord.ui.button(label="+1 Sanctuary", style=discord.ButtonStyle.success, custom_id="btn_count_sanctuary")
    async def add_sanctuary(self, interaction: discord.Interaction, button: discord.ui.Button):
        counts = self.use_case.increment_zone_count("sanctuary", 1)
        await interaction.response.edit_message(
            content=self.format_message(counts),
            view=self
        )

    @discord.ui.button(label="+1 Overflow", style=discord.ButtonStyle.secondary, custom_id="btn_count_overflow")
    async def add_overflow(self, interaction: discord.Interaction, button: discord.ui.Button):
        counts = self.use_case.increment_zone_count("overflow", 1)
        await interaction.response.edit_message(
            content=self.format_message(counts),
            view=self
        )

    @discord.ui.button(label="Reset", style=discord.ButtonStyle.danger, custom_id="btn_count_reset")
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        counts = self.use_case.reset_headcount()
        await interaction.response.edit_message(
            content=self.format_message(counts),
            view=self
        )

    def format_message(self, counts) -> str:
        return (
            f"**⛪ Live Attendance Count Update**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔴 **Sanctuary:** `{counts.sanctuary_count}` ushers/attendees\n"
            f"🟡 **Overflow:** `{counts.overflow_count}`\n"
            f"🔵 **Volunteers:** `{counts.volunteer_count}`\n"
            f"*Updated: {counts.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}*"
        )

class ServiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Tie to state manager
        self.use_case = CalculateCountsUseCase(bot.db)

    @app_commands.command(name="count", description="View and increment live sanctuary and overflow seat counts.")
    async def count(self, interaction: discord.Interaction):
        # Fetch current counts
        counts = self.use_case.get_current_headcount()
        view = CountView(self.use_case)
        
        # Add dynamic link button to the dashboard
        # Assuming hosted locally on default port 8000
        view.add_item(discord.ui.Button(
            label="Open Seating Map Dashboard",
            url="http://localhost:8000/src/presentation/web_dashboard/index.html",
            style=discord.ButtonStyle.link
        ))

        message_content = view.format_message(counts)
        await interaction.response.send_message(content=message_content, view=view)

async def setup(bot):
    await bot.add_cog(ServiceCog(bot))
