import discord
from discord import ui
from discord.ext import commands
from discord import app_commands
from src.infrastructure.planning_center.aio_client import PCOAsyncClient
from src.infrastructure.security.config import config
from src.domain.use_cases.reschedule_team import RescheduleTeamUseCase

class TeamSelect(ui.Select):
    def __init__(self, plan_data, member_map, status_map):
        self.plan_data = plan_data
        self.member_map = member_map
        self.status_map = status_map
        
        options = []
        for team_name in plan_data.get("detailed_teams", {}).keys():
            if len(options) >= 25:
                break
            options.append(discord.SelectOption(label=team_name, value=team_name))
            
        super().__init__(placeholder="Select teams to view...", min_values=1, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_teams = self.values
        lines = [f"📋 **Upcoming Plan: {self.plan_data['title']} ({self.plan_data.get('date', '')})**\n"]
        
        items = self.plan_data.get("items", [])
        if items:
            lines.append("📝 **All Service Items**")
            for idx, item in enumerate(items, 1):
                lines.append(f"{idx}. {item}")
            lines.append("")
        
        for team_name, members in self.plan_data.get("detailed_teams", {}).items():
            if team_name not in selected_teams:
                continue
                
            lines.append(f"👥 **{team_name}**")
            for m in members:
                pco_name = m['name']
                status_str = self.status_map.get(m.get('status', 'U'), "Pending")
                
                discord_id = self.member_map.get(pco_name.lower())
                if discord_id:
                    tag = f"<@{discord_id}>"
                else:
                    tag = f"@{pco_name}"
                    
                times_str = m.get('times_str', 'Any Time')
                if times_str == "Any Time":
                    lines.append(f"- {tag} ({status_str}) - {m['position']}")
                else:
                    lines.append(f"- {tag} ({status_str}) - {m['position']} - {times_str}")
            lines.append("")
            
        msg = "\n".join(lines)
        if len(msg) > 1900:
            msg = msg[:1900] + "...\n(Message truncated due to length)"
            
        await interaction.response.edit_message(content=msg, view=self.view)

class TeamFilterView(ui.View):
    def __init__(self, plan_data, member_map, status_map):
        super().__init__(timeout=None)
        if plan_data.get("detailed_teams"):
            self.add_item(TeamSelect(plan_data, member_map, status_map))

class RosterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        pco_client = PCOAsyncClient(config.pco_app_id, config.pco_secret)
        self.use_case = RescheduleTeamUseCase(pco_client)

    @app_commands.command(name="get_upcoming_plan", description="Retrieve the roster of the next service plan.")
    @app_commands.describe(
        service_type_id="Planning Center Service Type",
        team_filter="Optional: Only show a specific team (e.g. 'Worship Team')"
    )
    @app_commands.choices(service_type_id=[
        app_commands.Choice(name="RockChurch", value="89000"),
        app_commands.Choice(name="AMPD", value="1062544"),
        app_commands.Choice(name="RC Kids", value="1459775")
    ])
    async def get_upcoming_plan(self, interaction: discord.Interaction, service_type_id: app_commands.Choice[str], team_filter: str = None):
        service_id = service_type_id.value if isinstance(service_type_id, app_commands.Choice) else service_type_id
        await interaction.response.defer()
        plans = await self.use_case.get_upcoming_plan_roster(service_id)
        if not plans:
            await interaction.followup.send("⚠️ No upcoming plans found or PCO error.")
            return

        plan = plans[0]
        
        lines = [f"📋 **Upcoming Plan: {plan['title']} ({plan.get('date', '')})**\n"]
        
        items = plan.get("items", [])
        if items:
            lines.append("📝 **All Service Items**")
            for idx, item in enumerate(items, 1):
                lines.append(f"{idx}. {item}")
            lines.append("")
            
        detailed_teams = plan.get("detailed_teams", {})
        
        status_map = {
            "C": "Confirmed",
            "U": "Pending",
            "D": "Declined"
        }

        # Build discord member map to properly tag users
        member_map = {}
        if interaction.guild:
            for member in interaction.guild.members:
                member_map[member.display_name.lower()] = member.id
                member_map[member.name.lower()] = member.id

        if team_filter:
            if detailed_teams:
                for team_name, members in detailed_teams.items():
                    if team_filter.lower() not in team_name.lower():
                        continue
                    lines.append(f"👥 **{team_name}**")
                    for m in members:
                        pco_name = m['name']
                        status_str = status_map.get(m.get('status', 'U'), "Pending")
                        
                        discord_id = member_map.get(pco_name.lower())
                        if discord_id:
                            tag = f"<@{discord_id}>"
                        else:
                            tag = f"@{pco_name}"
                            
                        times_str = m.get('times_str', 'Any Time')
                        if times_str == "Any Time":
                            lines.append(f"- {tag} ({status_str}) - {m['position']}")
                        else:
                            lines.append(f"- {tag} ({status_str}) - {m['position']} - {times_str}")
                    lines.append("")
        else:
            if detailed_teams:
                lines.append("👇 **Please select the teams you want to view from the dropdown below.**")
        msg = "\n".join(lines)
        if len(msg) > 1900:
            msg = msg[:1900] + "...\n(Message truncated due to length)"
            
        view = TeamFilterView(plan, member_map, status_map)
        await interaction.followup.send(msg, view=view)

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
