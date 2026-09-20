import logging
from typing import List, Dict, Any, Optional
from src.domain.interfaces.pco_api import PlanningCenterAPI
from src.domain.entities.song import Song

logger = logging.getLogger(__name__)

class CheckUpcomingSongsUseCase:
    """
    Use case to check upcoming Planning Center service items:
    - If a plan item contains the word "Song" in its title, do nothing (skip).
    - Otherwise, if it is a linked song, extract: Artist, Title, Youtube Link, Lyrics PDF, Chords PDF.
    - If Youtube link is missing from the linked song, search and add it to the song in Planning Center.
    """
    def __init__(self, pco_api: PlanningCenterAPI):
        self.pco_api = pco_api

    async def execute(self, service_type_id: str = "89000") -> Dict[str, Any]:
        plans = await self.pco_api.get_upcoming_plans(service_type_id)
        if not plans:
            logger.warning(f"No upcoming plans found for service_type_id {service_type_id}")
            return {
                "plan_id": None,
                "plan_title": "No Upcoming Plan",
                "plan_date": "",
                "processed_songs": [],
                "skipped_items": []
            }

        plan = plans[0]
        plan_id = plan["id"]
        plan_title = plan.get("title", "Upcoming Service")
        plan_date = plan.get("date", "")

        # Get detailed plan items
        items = await self.pco_api.get_plan_items_detailed(service_type_id, plan_id)

        processed_songs: List[Dict[str, Any]] = []
        skipped_items: List[Dict[str, Any]] = []

        for item in items:
            title = item.get("title", "")
            title_lower = title.lower()

            # Rule: If item contains the word "Song", do nothing (skip)
            if "song" in title_lower:
                logger.info(f"Item '{title}' contains the word 'Song' -> skipping (do nothing).")
                skipped_items.append({
                    "id": item.get("id"),
                    "title": title,
                    "reason": "Contains the word 'Song'"
                })
                continue

            song_id = item.get("song_id")
            # If item has a linked song
            if song_id:
                song_details = await self.pco_api.get_song_details(song_id)
                song_title = song_details.get("title") or title
                artist = song_details.get("artist", "Unknown Artist")
                youtube_url = song_details.get("youtube_url")
                lyrics_pdf = song_details.get("lyrics_pdf_url")
                chords_pdf = song_details.get("chords_pdf_url")
                arrangement_id = song_details.get("arrangement_id")
                youtube_added = False

                # If Youtube link is missing, search and add it to the song
                if not youtube_url:
                    logger.info(f"YouTube link missing for song '{song_title}' by '{artist}'. Searching YouTube...")
                    yt_url = await self.pco_api.search_youtube(artist, song_title)
                    if yt_url:
                        success = await self.pco_api.add_youtube_link_to_song(
                            song_id=song_id,
                            youtube_url=yt_url,
                            arrangement_id=arrangement_id
                        )
                        if success:
                            youtube_url = yt_url
                            youtube_added = True
                            logger.info(f"Added YouTube link '{yt_url}' to song '{song_title}' in PCO.")

                processed_songs.append({
                    "song_id": song_id,
                    "title": song_title,
                    "artist": artist,
                    "youtube_url": youtube_url,
                    "lyrics_pdf_url": lyrics_pdf,
                    "chords_pdf_url": chords_pdf,
                    "youtube_added": youtube_added
                })

        return {
            "plan_id": plan_id,
            "plan_title": plan_title,
            "plan_date": plan_date,
            "processed_songs": processed_songs,
            "skipped_items": skipped_items
        }
