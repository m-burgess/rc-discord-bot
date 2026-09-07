import discord
from discord import ui
from discord.ext import commands
from discord import app_commands
from src.infrastructure.planning_center.aio_client import PCOAsyncClient
from src.infrastructure.security.config import config
from src.domain.use_cases.get_plan_roster import GetPlanRosterUseCase

class TeamSelect(ui.Select):
    def __init__(self, plan_data, member_map, status_map):
        self.plan_data = plan_data
        self.member_map = member_map
        self.status_map = status_map
        
        options = []
        detailed_teams = plan_data.get("detailed_teams", {})
        needed_positions = plan_data.get("needed_positions", {})
        all_teams = sorted(list(set(detailed_teams.keys()) | set(needed_positions.keys())))
        
        for team_name in all_teams:
            members = detailed_teams.get(team_name, [])
            team_needed = needed_positions.get(team_name, [])
            has_active = any(m.get("status", "U") != "D" for m in members)
            
            if not has_active and not team_needed:
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
        
        detailed_teams = self.plan_data.get("detailed_teams", {})
        needed_positions = self.plan_data.get("needed_positions", {})
        
        needs_signup_button = False
        
        for team_name in selected_teams:
            members = detailed_teams.get(team_name, [])
            active_members = [m for m in members if m.get('status', 'U') != 'D']
            team_needed = needed_positions.get(team_name, [])
            
            if not active_members and not team_needed:
                continue

            lines.append(f"👥 **{team_name}**")
            
            if not active_members:
                lines.append(f"⚠️ **NO ONE SCHEDULED**")
            else:
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

            if team_needed:
                needs_signup_button = True
                for np in team_needed:
                    lines.append(f"- Needed: {np['quantity']}x {np['position_name']}")
                    
            lines.append("")
            
        msg = "\n".join(lines)
        if len(msg) > 1900:
            msg = msg[:1900] + "...\n(Message truncated due to length)"
            
        # Rebuild view to keep dropdown, and add a signup button if needed
        self.view.clear_items()
        self.view.add_item(self) # add the dropdown back
        if needs_signup_button:
            self.view.add_item(discord.ui.Button(
                label="Sign Up in Planning Center", 
                url=f"https://services.planningcenteronline.com/plans/{self.plan_data['id']}",
                row=1
            ))
            
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
    "rc-kids-team": ["RC Kids", "Kids", "RC Babies team", "RC Babies", "RC Toddlers Team", "RC Toddlers", "RC Pre-school Team", "RC Pre-school", "Pre-school", "Fuse Team", "Fuse", "Babies", "Toddlers", "Nursery", "Pre-K", "Elementary"]
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
        self.use_case = GetPlanRosterUseCase(pco_client)

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

        needed_positions = plan.get("needed_positions", {})
        all_team_names = set(detailed_teams.keys()) | set(needed_positions.keys())
        needs_signup_button = False
        
        if mapped_teams:
            if all_team_names:
                for team_name in sorted(all_team_names):
                    if not matches_team(team_name, mapped_teams):
                        continue
                    
                    members = detailed_teams.get(team_name, [])
                    active_members = [m for m in members if m.get('status', 'U') != 'D']
                    team_needed = needed_positions.get(team_name, [])
                    
                    if not active_members and not team_needed:
                        continue
                        
                    lines.append(f"👥 **{team_name}**")
                    
                    if not active_members:
                        lines.append(f"⚠️ **NO ONE SCHEDULED**")
                    else:
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

                    if team_needed:
                        needs_signup_button = True
                        for np in team_needed:
                            lines.append(f"- Needed: {np['quantity']}x {np['position_name']}")
                            
                    lines.append("")
            show_dropdown = False
        elif team_filter:
            if all_team_names:
                for team_name in sorted(all_team_names):
                    if team_filter.lower() not in team_name.lower():
                        continue

                    members = detailed_teams.get(team_name, [])
                    active_members = [m for m in members if m.get('status', 'U') != 'D']
                    team_needed = needed_positions.get(team_name, [])
                    
                    if not active_members and not team_needed:
                        continue
                        
                    lines.append(f"👥 **{team_name}**")
                    
                    if not active_members:
                        lines.append(f"⚠️ **NO ONE SCHEDULED**")
                    else:
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

                    if team_needed:
                        needs_signup_button = True
                        for np in team_needed:
                            lines.append(f"- Needed: {np['quantity']}x {np['position_name']}")
                            
                    lines.append("")
            show_dropdown = False
        else:
            if all_team_names:
                lines.append("👇 **Please select the teams you want to view from the dropdown below.**")
                
        msg = "\n".join(lines)
        if len(msg) > 1900:
            msg = msg[:1900] + "...\n(Message truncated due to length)"
            
        if show_dropdown:
            view = TeamFilterView(plan, member_map, status_map)
            await interaction.followup.send(msg, view=view)
        else:
            view = None
            if needs_signup_button:
                view = discord.ui.View()
                view.add_item(discord.ui.Button(
                    label="Sign Up in Planning Center", 
                    url=f"https://services.planningcenteronline.com/plans/{plan['id']}"
                ))
            if view:
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

async def setup(bot):
    await bot.add_cog(RosterCog(bot))
