import discord
import logging
from datetime import datetime
import pytz
from discord.ext import tasks, commands
from discord import app_commands
from src.infrastructure.planning_center.aio_client import PCOAsyncClient
from src.infrastructure.security.config import config
from src.domain.use_cases.reschedule_team import RescheduleTeamUseCase
from src.presentation.cogs.roster_cog import CHANNEL_TEAM_MAP, matches_team

logger = logging.getLogger(__name__)

class ReminderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        pco_client = PCOAsyncClient(config.pco_app_id, config.pco_secret)
        self.use_case = RescheduleTeamUseCase(pco_client)
        # Start the background task loop
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()

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

            has_teams_for_channel = False
            for team_name, members in detailed_teams.items():
                if not matches_team(team_name, mapped_teams):
                    continue
                
                # Filter out declined members
                active_members = [m for m in members if m.get('status', 'U') != 'D']
                if not active_members:
                    continue

                has_teams_for_channel = True
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

            if has_teams_for_channel:
                msg = "\n".join(lines)
                if len(msg) > 1900:
                    msg = msg[:1900] + "...\n(Message truncated due to length)"
                try:
                    await channel.send(msg)
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
        tz = pytz.timezone("US/Central")
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
