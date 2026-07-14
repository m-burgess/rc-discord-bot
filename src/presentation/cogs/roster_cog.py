import discord
from discord.ext import commands
from discord import app_commands
from src.infrastructure.planning_center.aio_client import PCOAsyncClient
from src.infrastructure.security.config import config
from src.domain.use_cases.reschedule_team import RescheduleTeamUseCase

class RosterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        pco_client = PCOAsyncClient(config.pco_app_id, config.pco_secret)
        self.use_case = RescheduleTeamUseCase(pco_client)

    @app_commands.command(name="get_upcoming_plan", description="Retrieve the roster of the next service plan.")
    @app_commands.describe(service_type_id="Planning Center Service Type ID")
    async def get_upcoming_plan(self, interaction: discord.Interaction, service_type_id: str):
        await interaction.response.defer()
        plans = await self.use_case.get_upcoming_plan_roster(service_type_id)
        if not plans:
            await interaction.followup.send("⚠️ No upcoming plans found or PCO error.")
            return

        plan = plans[0]
        teams_str = "\n".join([f"- **{t['name']}**: {t['status']}" for t in plan.get("teams", [])])
        await interaction.followup.send(
            f"📋 **Upcoming Plan: {plan['title']} ({plan['date']})**\n{teams_str}"
        )

    # Autocomplete handler for teams
    async def team_autocomplete(self, interaction: discord.Interaction, current: str):
        # Default mock teams for autocomplete list
        teams = [
            app_commands.Choice(name="Audio Visual Team", value="team-audio"),
            app_commands.Choice(name="Host Team", value="team-host"),
            app_commands.Choice(name="Worship Band", value="team-worship"),
            app_commands.Choice(name="Production Crew", value="team-prod")
        ]
        return [t for t in teams if current.lower() in t.name.lower()]

    @app_commands.command(name="reschedule_upcoming_plan", description="Decline unconfirmed roster spots and auto-schedule replacements.")
    @app_commands.describe(plan_id="ID of the plan to update", team_id="Target team to reschedule")
    @app_commands.autocomplete(team_id=team_autocomplete)
    async def reschedule_upcoming_plan(self, interaction: discord.Interaction, plan_id: str, team_id: str):
        await interaction.response.defer()
        new_roster = await self.use_case.auto_schedule_and_clean_roster(plan_id, team_id)
        
        if not new_roster:
            await interaction.followup.send("⚠️ Failed to reschedule roster or no open spots could be auto-filled.")
            return

        roster_list = "\n".join([f"- <@{p.discord_id}> ({p.first_name} {p.last_name})" if p.discord_id else f"- {p.first_name} {p.last_name}" for p in new_roster])
        await interaction.followup.send(
            f"🔄 **Roster Updates for Plan `{plan_id}` (Team `{team_id}`):**\n"
            f"Automatically rescheduled replacement volunteers:\n{roster_list}"
        )

async def setup(bot):
    await bot.add_cog(RosterCog(bot))
