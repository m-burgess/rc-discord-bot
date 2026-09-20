import discord
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from discord.ext import tasks, commands
from discord import app_commands
from src.infrastructure.planning_center.aio_client import PCOAsyncClient
from src.infrastructure.security.config import config
from src.domain.use_cases.check_upcoming_songs import CheckUpcomingSongsUseCase

logger = logging.getLogger(__name__)

class SongCog(commands.Cog):
    """Cog for checking upcoming Planning Center service songs on Wednesday and Thursday afternoons."""

    def __init__(self, bot):
        self.bot = bot
        pco_client = PCOAsyncClient(config.pco_app_id, config.pco_secret)
        self.use_case = CheckUpcomingSongsUseCase(pco_client)
        self.check_afternoon_songs.start()

    def cog_unload(self):
        self.check_afternoon_songs.cancel()

    @tasks.loop(minutes=1)
    async def check_afternoon_songs(self):
        """Automated task running on Wednesday (2) and Thursday (3) afternoons at 2:00 PM (14:00) US/Central."""
        await self.bot.wait_until_ready()

        tz = ZoneInfo("US/Central")
        now = datetime.now(tz)
        current_day = now.weekday()  # Monday = 0, Wednesday = 2, Thursday = 3
        current_hour = now.hour
        current_minute = now.minute

        # Wednesday (2) and Thursday (3) at 14:00 (2:00 PM Central)
        if current_day in (2, 3) and current_hour == 14 and current_minute == 0:
            logger.info("Triggering automated Wednesday/Thursday afternoon PCO song check.")
            for guild in self.bot.guilds:
                self.bot.loop.create_task(self.run_and_broadcast_song_check(guild, "89000"))

    async def run_and_broadcast_song_check(self, guild: discord.Guild, service_type_id: str) -> discord.Embed:
        result = await self.use_case.execute(service_type_id)
        embed = self.build_song_report_embed(result)

        # Broadcast report to tech/worship channels if available
        target_channel = None
        for channel in guild.text_channels:
            if channel.name in ["rc-worship", "rc-tech-booth", "worship", "general"]:
                target_channel = channel
                break

        if target_channel:
            try:
                await target_channel.send(embed=embed)
                logger.info(f"Broadcasted song check report to {target_channel.name} in {guild.name}")
            except Exception as e:
                logger.error(f"Failed to send song report embed to {target_channel.name}: {e}")

        return embed

    def build_song_report_embed(self, result: dict) -> discord.Embed:
        plan_title = result.get("plan_title", "Upcoming Service")
        plan_date = result.get("plan_date", "")
        processed_songs = result.get("processed_songs", [])
        skipped_items = result.get("skipped_items", [])

        embed = discord.Embed(
            title=f"🎵 Planning Center Song Verification Report",
            description=f"**Plan:** {plan_title}\n**Date:** {plan_date}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        if processed_songs:
            for idx, song in enumerate(processed_songs, 1):
                title = song["title"]
                artist = song["artist"]
                yt_url = song.get("youtube_url")
                lyrics_url = song.get("lyrics_pdf_url")
                chords_url = song.get("chords_pdf_url")
                added_tag = " *(Automatically Added to PCO)*" if song.get("youtube_added") else ""

                links_list = []
                if yt_url:
                    links_list.append(f"[📺 YouTube Link]({yt_url}){added_tag}")
                else:
                    links_list.append("📺 YouTube Link: *Not Available*")

                if lyrics_url:
                    links_list.append(f"[📄 Lyrics PDF]({lyrics_url})")
                else:
                    links_list.append("📄 Lyrics PDF: *Not Available*")

                if chords_url:
                    links_list.append(f"[🎸 Chords PDF]({chords_url})")
                else:
                    links_list.append("🎸 Chords PDF: *Not Available*")

                value_str = f"**Artist:** {artist}\n" + "\n".join(links_list)
                embed.add_field(
                    name=f"{idx}. {title}",
                    value=value_str,
                    inline=False
                )
        else:
            embed.add_field(
                name="🎶 Linked Songs",
                value="No linked songs found in this plan.",
                inline=False
            )

        if skipped_items:
            skipped_names = [f"• `{item['title']}`" for item in skipped_items]
            embed.add_field(
                name="⏭️ Items Containing 'Song' (Skipped)",
                value="\n".join(skipped_names),
                inline=False
            )

        embed.set_footer(text="RC Bot • Planning Center Service Song Audit")
        return embed

    @app_commands.command(
        name="check_upcoming_songs",
        description="Check upcoming Planning Center service items for linked songs, grab links/PDFs, and auto-add missing YouTube links."
    )
    @app_commands.describe(service_type_id="Select Planning Center Service Type")
    @app_commands.choices(service_type_id=[
        app_commands.Choice(name="RockChurch", value="89000"),
        app_commands.Choice(name="AMPD", value="1062544"),
        app_commands.Choice(name="RC Kids", value="1459775")
    ])
    @app_commands.default_permissions(administrator=True)
    async def check_upcoming_songs(
        self,
        interaction: discord.Interaction,
        service_type_id: app_commands.Choice[str]
    ):
        service_id = service_type_id.value if isinstance(service_type_id, app_commands.Choice) else service_type_id
        await interaction.response.defer(ephemeral=False)

        result = await self.use_case.execute(service_id)
        embed = self.build_song_report_embed(result)

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SongCog(bot))
