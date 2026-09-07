import discord
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from discord.ext import tasks, commands
from discord import app_commands
from src.infrastructure.planning_center.aio_client import PCOAsyncClient
from src.infrastructure.security.config import config
from src.domain.use_cases.get_plan_roster import GetPlanRosterUseCase
from src.presentation.cogs.roster_cog import CHANNEL_TEAM_MAP, matches_team

logger = logging.getLogger(__name__)

class ReminderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        pco_client = PCOAsyncClient(config.pco_app_id, config.pco_secret)
        self.use_case = GetPlanRosterUseCase(pco_client)
        # Start the background task loop
        self.check_reminders.start()
        self.check_office_manager_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()
        self.check_office_manager_reminders.cancel()

    async def broadcast_roster(self, guild: discord.Guild, service_type_id: str):
        """Fetches the plan and broadcasts filtered rosters to mapped channels."""
        plans = await self.use_case.get_upcoming_plan_roster(service_type_id)
        if not plans:
            logger.warning(f"No upcoming plans found for service_type {service_type_id} during reminder broadcast.")
            return

        plan = plans[0]
        detailed_teams = plan.get("detailed_teams", {})
        if not detailed_teams:
            return

        status_map = {
            "C": "Confirmed",
            "U": "Pending",
            "D": "Declined"
        }

        # Build discord member map to properly tag users
        member_map = {}
        for member in guild.members:
            member_map[member.display_name.lower()] = member.id
            member_map[member.name.lower()] = member.id

        logger.info(f"Broadcast fetched plan '{plan['title']}' with team rosters: {list(detailed_teams.keys())}")

        # Iterate through mapped channels in the guild
        for channel in guild.text_channels:
            mapped_teams = CHANNEL_TEAM_MAP.get(channel.name)
            if not mapped_teams:
                continue

            lines = [f"⏰ **Automated Roster Reminder**"]
            lines.append(f"📋 **Upcoming Plan: {plan['title']} ({plan.get('date', '')})**\n")
            
            # Print the items first
            items = plan.get("items", [])
            if items:
                lines.append("📝 **All Service Items**")
                for idx, item in enumerate(items, 1):
                    lines.append(f"{idx}. {item}")
                lines.append("")

            needed_positions = plan.get("needed_positions", {})
            all_team_names = set(detailed_teams.keys()) | set(needed_positions.keys())
            
            has_teams_for_channel = False
            needs_signup_button = False
            
            for team_name in sorted(all_team_names):
                if not matches_team(team_name, mapped_teams):
                    continue
                
                members = detailed_teams.get(team_name, [])
                active_members = [m for m in members if m.get('status', 'U') != 'D']
                team_needed = needed_positions.get(team_name, [])
                
                if not active_members and not team_needed:
                    continue

                has_teams_for_channel = True
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
                        times_str = np.get("times_str", "Any Time")
                        if times_str == "Any Time":
                            lines.append(f"- Needed: {np['quantity']}x {np['position_name']}")
                        else:
                            lines.append(f"- Needed: {np['quantity']}x {np['position_name']} - {times_str}")
                        
                lines.append("")

            if has_teams_for_channel:
                msg = "\n".join(lines)
                if len(msg) > 1900:
                    msg = msg[:1900] + "...\n(Message truncated due to length)"
                try:
                    view = None
                    if needs_signup_button:
                        view = discord.ui.View()
                        view.add_item(discord.ui.Button(
                            label="Sign Up in Planning Center", 
                            url=f"https://services.planningcenteronline.com/plans/{plan['id']}"
                        ))
                    await channel.send(msg, view=view)
                except discord.Forbidden:
                    logger.warning(f"Missing permissions to send reminder to {channel.name}")
                except Exception as e:
                    logger.error(f"Failed to send reminder to {channel.name}: {e}")


    @tasks.loop(minutes=1)
    async def check_reminders(self):
        """Checks the database for reminders that match the current day and time."""
        # Ensure we don't run until bot is ready
        await self.bot.wait_until_ready()
        
        # Get current time in US/Central
        tz = ZoneInfo("US/Central")
        now = datetime.now(tz)
        current_day = now.weekday()  # Monday is 0, Sunday is 6
        current_hour = now.hour
        current_minute = now.minute

        try:
            # We assume bot.db is the SQLiteStateManager
            reminders = self.bot.db.get_all_reminders()
            for r in reminders:
                if (r["day_of_week"] == current_day and 
                    r["hour"] == current_hour and 
                    r["minute"] == current_minute):
                    
                    guild_id = int(r["guild_id"])
                    guild = self.bot.get_guild(guild_id)
                    if guild:
                        logger.info(f"Triggering automated reminder for guild {guild_id}, service {r['service_type_id']}")
                        # Trigger broadcast asynchronously so we don't block the loop
                        self.bot.loop.create_task(self.broadcast_roster(guild, r["service_type_id"]))
                    else:
                        logger.warning(f"Guild {guild_id} not found when checking reminders.")
        except Exception as e:
            logger.error(f"Error checking reminders: {e}")
            
        # Check for automated pending DMs on Wednesday (2) and Friday (4) at 10:00 AM
        if current_day in (2, 4) and current_hour == 10 and current_minute == 0:
            try:
                reminders = self.bot.db.get_all_reminders()
                checked_combos = set()
                for r in reminders:
                    combo = (r["guild_id"], r["service_type_id"])
                    if combo not in checked_combos:
                        checked_combos.add(combo)
                        guild = self.bot.get_guild(int(r["guild_id"]))
                        if guild:
                            self.bot.loop.create_task(self.send_pending_dms(guild, r["service_type_id"]))
            except Exception as e:
                logger.error(f"Error checking pending DMs: {e}")

    async def send_pending_dms(self, guild: discord.Guild, service_type_id: str):
        from src.presentation.views.roster_status_view import RosterStatusView
        plans = await self.use_case.get_upcoming_plan_roster(service_type_id)
        if not plans:
            return

        plan = plans[0]
        detailed_teams = plan.get("detailed_teams", {})
        if not detailed_teams:
            return

        member_map = {}
        for member in guild.members:
            member_map[member.display_name.lower()] = member
            member_map[member.name.lower()] = member

        for team_name, members in detailed_teams.items():
            for m in members:
                if m.get('status') == 'U':
                    discord_member = member_map.get(m['name'].lower())
                    if discord_member:
                        try:
                            view = RosterStatusView(self.pco_client, service_type_id, plan['id'], m['id'])
                            msg = f"👋 Hi {m['name']}! You are scheduled for **{team_name}** on **{plan.get('date', 'Upcoming Service')}**.\n\nPlease confirm or decline your schedule."
                            await discord_member.send(content=msg, view=view)
                            logger.info(f"Sent pending DM to {m['name']} for {team_name}")
                        except discord.Forbidden:
                            logger.warning(f"Could not send DM to {m['name']}")
                        except Exception as e:
                            logger.error(f"Error sending DM to {m['name']}: {e}")

    async def send_office_manager_dm(self, guild: discord.Guild, service_type_id: str, target_time_str: str):
        """Fetches the plan and sends a DM to the RC Office Manager with the filtered roster."""
        plans = await self.use_case.get_upcoming_plan_roster(service_type_id)
        if not plans:
            logger.warning(f"No upcoming plans found for service_type {service_type_id} during office manager broadcast.")
            return

        plan = plans[0]
        detailed_teams = plan.get("detailed_teams", {})
        needed_positions = plan.get("needed_positions", {})
        
        status_map = {
            "C": "Confirmed",
            "U": "Pending",
            "D": "Declined"
        }

        # Build discord member map
        member_map = {}
        for member in guild.members:
            member_map[member.display_name.lower()] = member.id
            member_map[member.name.lower()] = member.id

        lines = [f"⏰ **Office Manager Scheduled Roster**"]
        lines.append(f"📋 **Upcoming Plan: {plan['title']} ({plan.get('date', '')})**\n")
        lines.append(f"🔎 **Filtered for: {target_time_str}**\n")

        all_team_names = set(detailed_teams.keys()) | set(needed_positions.keys())
        has_teams = False

        for team_name in sorted(all_team_names):
            members = detailed_teams.get(team_name, [])
            # Filter members by time_str
            active_members = []
            for m in members:
                if m.get('status', 'U') == 'D':
                    continue
                times_str = m.get('times_str', 'Any Time')
                if times_str == "Any Time" or target_time_str in times_str:
                    active_members.append(m)

            # Filter needed positions by time
            team_needed = []
            for np in needed_positions.get(team_name, []):
                times_str = np.get('times_str', 'Any Time')
                if times_str == "Any Time" or target_time_str in times_str:
                    team_needed.append(np)

            if not active_members and not team_needed:
                continue

            has_teams = True
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
                for np in team_needed:
                    times_str = np.get("times_str", "Any Time")
                    if times_str == "Any Time":
                        lines.append(f"- Needed: {np['quantity']}x {np['position_name']}")
                    else:
                        lines.append(f"- Needed: {np['quantity']}x {np['position_name']} - {times_str}")
                    
            lines.append("")

        if not has_teams:
            return

        msg = "\n".join(lines)
        if len(msg) > 1900:
            msg = msg[:1900] + "...\n(Message truncated due to length)"

        # Find office managers
        office_managers = []
        for member in guild.members:
            for role in member.roles:
                if role.name.lower() == "rc office manager":
                    office_managers.append(member)
                    break

        if not office_managers:
            logger.warning("No RC Office Manager found to DM.")
            return

        for om in office_managers:
            try:
                await om.send(msg)
                logger.info(f"Sent Office Manager DM to {om.name}")
            except discord.Forbidden:
                logger.warning(f"Missing permissions to send DM to {om.name}")
            except Exception as e:
                logger.error(f"Failed to send DM to {om.name}: {e}")

    @tasks.loop(minutes=1)
    async def check_office_manager_reminders(self):
        """Checks if it's time to send the Office Manager direct messages."""
        await self.bot.wait_until_ready()
        
        tz = ZoneInfo("US/Central")
        now = datetime.now(tz)
        current_day = now.weekday()
        current_hour = now.hour
        current_minute = now.minute

        # Configuration: (day_of_week, hour, minute) -> target_time_str
        schedules = [
            (5, 16, 0, "5:00 PM"),
            (6, 7, 0, "9:00 AM"),
            (6, 10, 0, "11:00 AM"),
        ]
        
        for (day, hr, mn, target_time_str) in schedules:
            if current_day == day and current_hour == hr and current_minute == mn:
                for guild in self.bot.guilds:
                    logger.info(f"Triggering automated Office Manager reminder for guild {guild.id}, time: {target_time_str}")
                    self.bot.loop.create_task(self.send_office_manager_dm(guild, "89000", target_time_str))

    @app_commands.command(name="test_office_manager_reminder", description="Instantly trigger the Office Manager DM for testing.")
    @app_commands.describe(
        service_type_id="Planning Center Service Type",
        target_time_str="Target time string to filter (e.g. '5:00 PM', '9:00 AM', '11:00 AM')"
    )
    @app_commands.choices(service_type_id=[
        app_commands.Choice(name="RockChurch", value="89000"),
        app_commands.Choice(name="AMPD", value="1062544"),
        app_commands.Choice(name="RC Kids", value="1459775")
    ])
    @app_commands.default_permissions(administrator=True)
    async def test_office_manager_reminder(self, interaction: discord.Interaction, service_type_id: app_commands.Choice[str], target_time_str: str):
        service_id = service_type_id.value if isinstance(service_type_id, app_commands.Choice) else service_type_id
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.guild:
            await interaction.followup.send("This command must be used in a server.")
            return

        await interaction.followup.send(f"⏳ Fetching plan and sending Office Manager DM filtered for '{target_time_str}'...")
        await self.send_office_manager_dm(interaction.guild, service_id, target_time_str)
        await interaction.followup.send("✅ Test Office Manager DM complete!")

    @app_commands.command(name="test_reminder", description="Instantly trigger a schedule reminder broadcast for testing.")
    @app_commands.describe(service_type_id="Planning Center Service Type")
    @app_commands.choices(service_type_id=[
        app_commands.Choice(name="RockChurch", value="89000"),
        app_commands.Choice(name="AMPD", value="1062544"),
        app_commands.Choice(name="RC Kids", value="1459775")
    ])
    @app_commands.default_permissions(administrator=True)
    async def test_reminder(self, interaction: discord.Interaction, service_type_id: app_commands.Choice[str]):
        service_id = service_type_id.value if isinstance(service_type_id, app_commands.Choice) else service_type_id
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.guild:
            await interaction.followup.send("This command must be used in a server.")
            return

        await interaction.followup.send("⏳ Fetching plan and broadcasting to team channels...")
        await self.broadcast_roster(interaction.guild, service_id)
        await interaction.followup.send("✅ Test broadcast complete!")

    @app_commands.command(name="set_reminder", description="Set up an automated weekly reminder for the rosters.")
    @app_commands.describe(
        service_type_id="Planning Center Service Type",
        day_of_week="Day of the week (e.g., 'Wednesday', 'Thursday')",
        time="Time in HH:MM (24-hour format, Central Time, e.g. 14:30)"
    )
    @app_commands.choices(service_type_id=[
        app_commands.Choice(name="RockChurch", value="89000"),
        app_commands.Choice(name="AMPD", value="1062544"),
        app_commands.Choice(name="RC Kids", value="1459775")
    ])
    @app_commands.choices(day_of_week=[
        app_commands.Choice(name="Monday", value="0"),
        app_commands.Choice(name="Tuesday", value="1"),
        app_commands.Choice(name="Wednesday", value="2"),
        app_commands.Choice(name="Thursday", value="3"),
        app_commands.Choice(name="Friday", value="4"),
        app_commands.Choice(name="Saturday", value="5"),
        app_commands.Choice(name="Sunday", value="6"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def set_reminder(self, interaction: discord.Interaction, service_type_id: app_commands.Choice[str], day_of_week: app_commands.Choice[str], time: str):
        try:
            hour_str, minute_str = time.split(":")
            hour = int(hour_str)
            minute = int(minute_str)
            if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                raise ValueError("Invalid time range")
        except ValueError:
            await interaction.response.send_message("❌ Invalid time format! Please use HH:MM in 24-hour time (e.g., 14:30 for 2:30 PM).", ephemeral=True)
            return

        service_id = service_type_id.value if isinstance(service_type_id, app_commands.Choice) else service_type_id
        day = int(day_of_week.value if isinstance(day_of_week, app_commands.Choice) else day_of_week)
        guild_id = str(interaction.guild_id)

        try:
            self.bot.db.set_reminder(guild_id, service_id, day, hour, minute)
            day_name = day_of_week.name if hasattr(day_of_week, 'name') else day_of_week
            await interaction.response.send_message(f"✅ Successfully scheduled an automated reminder!\n**Service:** `{service_type_id.name if hasattr(service_type_id, 'name') else service_id}`\n**Schedule:** Every {day_name} at {time} (US/Central).", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to set reminder: {e}")
            await interaction.response.send_message("❌ An error occurred while saving the reminder.", ephemeral=True)

    async def reminder_autocomplete(self, interaction: discord.Interaction, current: str):
        reminders = self.bot.db.get_all_reminders()
        guild_id = str(interaction.guild_id)
        choices = []
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for r in reminders:
            if str(r["guild_id"]) == guild_id:
                day_name = days[r["day_of_week"]]
                time_str = f"{r['hour']:02d}:{r['minute']:02d}"
                label = f"ID: {r['id']} | Service: {r['service_type_id']} | {day_name} at {time_str}"
                if current.lower() in label.lower():
                    choices.append(app_commands.Choice(name=label[:100], value=str(r['id'])))
        return choices[:25]

    @app_commands.command(name="delete_reminder", description="Delete an active automated reminder.")
    @app_commands.describe(reminder_id="Select the reminder to delete.")
    @app_commands.autocomplete(reminder_id=reminder_autocomplete)
    @app_commands.default_permissions(administrator=True)
    async def delete_reminder(self, interaction: discord.Interaction, reminder_id: str):
        try:
            r_id = int(reminder_id)
            deleted = self.bot.db.delete_reminder(r_id)
            if deleted:
                await interaction.response.send_message(f"✅ Successfully deleted reminder.", ephemeral=True)
            else:
                await interaction.response.send_message(f"⚠️ Reminder not found.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid reminder ID.", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to delete reminder: {e}")
            await interaction.response.send_message("❌ An error occurred while deleting the reminder.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ReminderCog(bot))
