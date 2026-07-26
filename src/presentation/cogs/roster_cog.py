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
        for team_name, members in plan_data.get("detailed_teams", {}).items():
            if not any(m.get("status", "U") != "D" for m in members):
                continue
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
                
            active_members = [m for m in members if m.get('status', 'U') != 'D']
            if not active_members:
                continue

            lines.append(f"👥 **{team_name}**")
            for m in active_members:
                pco_name = m['name']
                status_code = m.get('status', 'U')
                status_str = self.status_map.get(status_code, "Pending")
                
                discord_id = self.member_map.get(pco_name.lower())
                if discord_id:
                    tag = f"<@{discord_id}>"
                else:
                    tag = pco_name
                    
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

CHANNEL_TEAM_MAP = {
    "rc-tech-booth": ["Sound Booth", "Media", "Video Production"],
    "rc-coffee-bar": ["RC Coffee Bar", "Coffee Bar"],
    "rc-safety-team": ["Safety Team", "Safety"],
    "rc-next-steps-booth": ["VIP Booth | Merch", "VIP Booth", "Merch", "Next Steps"],
    "rc-worship": ["Worship Team", "Worship"],
    "rc-greeter-team": ["Welcome Team", "Greeter", "Greeters"],
    "rc-emcee-team": ["Emcee Team", "Emcee", "Emcees"],
    "rc-usher-team": ["Ushers", "Usher"],
    "rc-offering-count": ["Offering Count", "Offering Counter", "Offering Counters", "Offering"],
    "rc-parking-team": ["Parking Team", "Parking"],
    "rc-kids-team": ["RC Kids", "Kids"]
}

def matches_team(pco_team_name: str, mapped_teams: list) -> bool:
    pco_clean = pco_team_name.lower().strip()
    for target in mapped_teams:
        t_clean = target.lower().strip()
        if t_clean in pco_clean or pco_clean in t_clean:
            return True
    return False

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

        channel_name = interaction.channel.name if hasattr(interaction.channel, 'name') else ""
        mapped_teams = CHANNEL_TEAM_MAP.get(channel_name)

        show_dropdown = True

        if mapped_teams:
            if detailed_teams:
                for team_name, members in detailed_teams.items():
                    if not matches_team(team_name, mapped_teams):
                        continue
                    
                    active_members = [m for m in members if m.get('status', 'U') != 'D']
                    if not active_members:
                        continue

                    lines.append(f"👥 **{team_name}**")
                    for m in active_members:
                        pco_name = m['name']
                        status_code = m.get('status', 'U')
                        status_str = status_map.get(status_code, "Pending")
                        
                        discord_id = member_map.get(pco_name.lower())
                        if discord_id:
                            tag = f"<@{discord_id}>"
                        else:
                            tag = pco_name
                            
                        times_str = m.get('times_str', 'Any Time')
                        if times_str == "Any Time":
                            lines.append(f"- {tag} ({status_str}) - {m['position']}")
                        else:
                            lines.append(f"- {tag} ({status_str}) - {m['position']} - {times_str}")
                    lines.append("")
            show_dropdown = False
        elif team_filter:
            if detailed_teams:
                for team_name, members in detailed_teams.items():
                    if team_filter.lower() not in team_name.lower():
                        continue

                    active_members = [m for m in members if m.get('status', 'U') != 'D']
                    if not active_members:
                        continue

                    lines.append(f"👥 **{team_name}**")
                    for m in active_members:
                        pco_name = m['name']
                        status_code = m.get('status', 'U')
                        status_str = status_map.get(status_code, "Pending")
                        
                        discord_id = member_map.get(pco_name.lower())
                        if discord_id:
                            tag = f"<@{discord_id}>"
                        else:
                            tag = pco_name
                            
                        times_str = m.get('times_str', 'Any Time')
                        if times_str == "Any Time":
                            lines.append(f"- {tag} ({status_str}) - {m['position']}")
                        else:
                            lines.append(f"- {tag} ({status_str}) - {m['position']} - {times_str}")
                    lines.append("")
            show_dropdown = False
        else:
            if detailed_teams:
                lines.append("👇 **Please select the teams you want to view from the dropdown below.**")
                
        msg = "\n".join(lines)
        if len(msg) > 1900:
            msg = msg[:1900] + "...\n(Message truncated due to length)"
            
        if show_dropdown:
            view = TeamFilterView(plan, member_map, status_map)
            await interaction.followup.send(msg, view=view)
        else:
            await interaction.followup.send(msg)

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
