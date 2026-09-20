import pytest
from src.domain.use_cases.check_upcoming_songs import CheckUpcomingSongsUseCase
from src.infrastructure.planning_center.aio_client import PCOAsyncClient

class MockSongPCO:
    def __init__(self):
        self.added_youtube_links = []

    async def get_upcoming_plans(self, service_type_id: str):
        return [{
            "id": "plan-99",
            "title": "Sunday Morning Service",
            "date": "2026-09-24T10:00:00Z"
        }]

    async def get_plan_items_detailed(self, service_type_id: str, plan_id: str):
        return [
            {"id": "item-1", "title": "Welcome & Prayer", "item_type": "header", "song_id": None},
            {"id": "item-2", "title": "Song", "item_type": "item", "song_id": None},
            {"id": "item-3", "title": "Opening Song", "item_type": "item", "song_id": None},
            {"id": "item-4", "title": "Holy Forever", "item_type": "song", "song_id": "song-1", "arrangement_id": "arr-1"},
            {"id": "item-5", "title": "Goodness of God", "item_type": "song", "song_id": "song-2", "arrangement_id": "arr-2"},
        ]

    async def get_song_details(self, song_id: str):
        if song_id == "song-1":
            return {
                "id": "song-1",
                "title": "Holy Forever",
                "artist": "Chris Tomlin",
                "youtube_url": "https://www.youtube.com/watch?v=holy123",
                "lyrics_pdf_url": "https://pco.com/lyrics_holy_forever.pdf",
                "chords_pdf_url": "https://pco.com/chords_holy_forever.pdf",
                "arrangement_id": "arr-1"
            }
        elif song_id == "song-2":
            # Missing YouTube link to test auto-adding
            return {
                "id": "song-2",
                "title": "Goodness of God",
                "artist": "Bethel Music",
                "youtube_url": None,
                "lyrics_pdf_url": "https://pco.com/lyrics_goodness_of_god.pdf",
                "chords_pdf_url": "https://pco.com/chords_goodness_of_god.pdf",
                "arrangement_id": "arr-2"
            }

    async def search_youtube(self, artist: str, title: str):
        return f"https://www.youtube.com/watch?v=auto_{title.lower().replace(' ', '_')}"

    async def add_youtube_link_to_song(self, song_id: str, youtube_url: str, arrangement_id: str = None):
        self.added_youtube_links.append((song_id, youtube_url))
        return True

@pytest.mark.asyncio
async def test_check_upcoming_songs_use_case():
    pco = MockSongPCO()
    use_case = CheckUpcomingSongsUseCase(pco)

    result = await use_case.execute("89000")

    assert result["plan_id"] == "plan-99"
    assert result["plan_title"] == "Sunday Morning Service"
    
    # Items containing the word 'Song' should be skipped
    skipped = result["skipped_items"]
    assert len(skipped) == 2
    skipped_titles = [item["title"] for item in skipped]
    assert "Song" in skipped_titles
    assert "Opening Song" in skipped_titles

    # Processed songs
    processed = result["processed_songs"]
    assert len(processed) == 2

    # Song 1: Holy Forever (already had YouTube link)
    song1 = processed[0]
    assert song1["title"] == "Holy Forever"
    assert song1["artist"] == "Chris Tomlin"
    assert song1["youtube_url"] == "https://www.youtube.com/watch?v=holy123"
    assert song1["lyrics_pdf_url"] == "https://pco.com/lyrics_holy_forever.pdf"
    assert song1["chords_pdf_url"] == "https://pco.com/chords_holy_forever.pdf"
    assert song1["youtube_added"] is False

    # Song 2: Goodness of God (missing YouTube link, auto-added)
    song2 = processed[1]
    assert song2["title"] == "Goodness of God"
    assert song2["artist"] == "Bethel Music"
    assert song2["youtube_url"] == "https://www.youtube.com/watch?v=auto_goodness_of_god"
    assert song2["lyrics_pdf_url"] == "https://pco.com/lyrics_goodness_of_god.pdf"
    assert song2["chords_pdf_url"] == "https://pco.com/chords_goodness_of_god.pdf"
    assert song2["youtube_added"] is True
    assert len(pco.added_youtube_links) == 1
    assert pco.added_youtube_links[0] == ("song-2", "https://www.youtube.com/watch?v=auto_goodness_of_god")

@pytest.mark.asyncio
async def test_pco_client_mock_integration():
    client = PCOAsyncClient("MOCK_PCO_APP_ID", "MOCK_SECRET")
    use_case = CheckUpcomingSongsUseCase(client)

    result = await use_case.execute("89000")
    assert result["plan_id"] is not None
    assert len(result["processed_songs"]) > 0
    assert len(result["skipped_items"]) > 0
