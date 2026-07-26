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

    @app_commands.command(name="how-does-this-work", description="Admin overview of the RC Bot architecture, hosting, and services.")
    @app_commands.default_permissions(administrator=True)
    async def how_does_this_work(self, interaction: discord.Interaction):
        info_text = (
            "🤖 **RC Bot System Overview & Architecture**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🖥️ **Hosting & Deployment:**\n"
            "• Running locally on the **Church Office Computer** (Linux environment).\n"
            "• Managed in a synced office folder. Deploying updates is as simple as updating the project directory or pulling from GitHub.\n"
            "• **Public Codebase:** <https://github.com/m-burgess/rc-discord-bot>\n\n"
            "🛠️ **Core Technologies & Architecture:**\n"
            "• **Framework:** Built using Python `discord.py` with Clean Architecture.\n"
            "• **Security:** Integrates with **Bitwarden Secrets Manager** for safe runtime credential loading.\n\n"
            "🔌 **Connected Tech Services & Integrations:**\n"
            "• 📋 **Planning Center Services & People:**\n"
            "  - Automated weekly schedule reminders & roster lookups.\n"
            "  - Dynamic Discord user mentions for scheduled volunteers.\n"
            "  - Church Center household registration form integration.\n"
            "• 🎛️ **Production Hardware Controls:**\n"
            "  - **Behringer WING** (OSC / UDP Control)\n"
            "  - **Blackmagic ATEM Switcher** (Network API)\n"
            "  - **Blackmagic Cameras** (IP Control)\n"
            "• ⏰ **Automated Background Scheduler:**\n"
            "  - Continuously checks SQLite schedule rules to auto-broadcast team rosters to mapped channel chats (`#rc-tech-booth`, `#rc-worship`, `#rc-coffee-bar`, etc.)."
        )
        await interaction.response.send_message(info_text, ephemeral=True)

    @app_commands.command(name="how-to-create-new-command", description="Step-by-step developer guide for adding new commands/features to RC Bot.")
    @app_commands.default_permissions(administrator=True)
    async def how_to_create_new_command(self, interaction: discord.Interaction):
        guide_text = (
            "🛠️ **Guide: How to Add a New Command to RC Bot**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "1️⃣ **Locate the Right Cog:**\n"
            "• Open `src/presentation/cogs/` on the office computer.\n"
            "• Pick an existing file (e.g. `service_cog.py`, `roster_cog.py`) or create a new `*_cog.py`.\n\n"
            "2️⃣ **Write the Slash Command:**\n"
            "```python\n"
            "@app_commands.command(name=\"my-command\", description=\"Description\")\n"
            "@app_commands.default_permissions(administrator=True) # Optional\n"
            "async def my_command(self, interaction: discord.Interaction):\n"
            "    await interaction.response.send_message(\"Hello World!\", ephemeral=True)\n"
            "```\n\n"
            "3️⃣ **Register New Cog (If New File):**\n"
            "• Open `src/presentation/bot.py` and add `\"src.presentation.cogs.new_cog\"` to the `cogs` list in `setup_hook()`.\n\n"
            "4️⃣ **Restart Bot & Sync Commands:**\n"
            "• Restart the bot script (`python src/presentation/bot.py`).\n"
            "• Type `!sync` in Discord to force an instant command synchronization to your server!\n\n"
            "💡 *Architecture Note: Use `src/domain/` for business logic, `src/infrastructure/` for APIs/DB, and `src/presentation/cogs/` for Discord UI.*"
        )
        await interaction.response.send_message(guide_text, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ServiceCog(bot))
