import aiohttp
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from src.domain.interfaces.pco_api import PlanningCenterAPI
from src.domain.entities.checkin import CheckIn, Person

logger = logging.getLogger(__name__)

class PCOAsyncClient(PlanningCenterAPI):
    def __init__(self, app_id: str, secret: str):
        self.app_id = app_id
        self.secret = secret
        self.is_mock = (app_id == "MOCK_PCO_APP_ID" or not app_id)

    def _get_auth(self) -> Optional[aiohttp.BasicAuth]:
        if self.is_mock:
            return None
        return aiohttp.BasicAuth(self.app_id, self.secret)

    async def get_checkins(self, date_str: str) -> List[CheckIn]:
        if self.is_mock:
            logger.warning("PCO: using MOCK check-ins.")
            return []

        url = f"https://api.planningcenteronline.com/check-ins/v2/check_ins?include=person&filter=date&date={date_str}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=self._get_auth()) as response:
                if response.status != 200:
                    logger.error(f"PCO API error on get_checkins: status code {response.status}")
                    return []
                
                data = await response.json()
                
                # Parse included persons
                included = data.get("included", [])
                people_map = {}
                for inc in included:
                    if inc.get("type") == "Person":
                        people_map[inc.get("id")] = inc.get("attributes", {})

                checkins = []
                for item in data.get("data", []):
                    rel = item.get("relationships", {})
                    person_id = rel.get("person", {}).get("data", {}).get("id")
                    
                    p_attrs = people_map.get(person_id, {})
                    first_name = p_attrs.get("first_name", "Unknown")
                    last_name = p_attrs.get("last_name", "Unknown")
                    
                    created_at = item.get("attributes", {}).get("created_at")
                    dt = datetime.utcnow()
                    if created_at:
                        try:
                            dt = datetime.strptime(created_at[:19], "%Y-%m-%dT%H:%M:%S")
                        except Exception:
                            pass

                    checkins.append(
                        CheckIn(
                            id=item.get("id"),
                            person=Person(id=person_id or "unknown", first_name=first_name, last_name=last_name),
                            checked_in_at=dt,
                            location="Checked In"
                        )
                    )
                return checkins

    async def get_people_by_team(self, team_id: str) -> List[Person]:
        if self.is_mock:
            return []
            
        url = f"https://api.planningcenteronline.com/services/v2/teams/{team_id}/people"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=self._get_auth()) as response:
                if response.status != 200:
                    logger.error(f"PCO API error on get_people_by_team: status code {response.status}")
                    return []
                data = await response.json()
                people = []
                for item in data.get("data", []):
                    attrs = item.get("attributes", {})
                    people.append(Person(
                        id=item.get("id"),
                        first_name=attrs.get("first_name", "Unknown"),
                        last_name=attrs.get("last_name", "Unknown")
                    ))
                return people

    async def check_in_person(self, person_id: str, location_id: str) -> bool:
        if self.is_mock:
            return True
            
        url = "https://api.planningcenteronline.com/check-ins/v2/check_ins"
        payload = {
            "data": {
                "type": "CheckIn",
                "attributes": {},
                "relationships": {
                    "person": {"data": {"type": "Person", "id": person_id}},
                    "location": {"data": {"type": "Location", "id": location_id}}
                }
            }
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, auth=self._get_auth()) as response:
                if response.status in [200, 201]:
                    return True
                logger.error(f"Failed to check in: {response.status}")
                return False

    async def check_out_person(self, checkin_id: str) -> bool:
        if self.is_mock:
            return True
        return False # Real checkout is complex in PCO

    async def get_upcoming_plans(self, service_type_id: str) -> List[Dict[str, Any]]:
        if self.is_mock:
            return [{
                "id": "plan-mock-1",
                "title": "Sunday Worship Service",
                "date": "2026-09-27T10:00:00Z",
                "teams": []
            }]
            
        url = f"https://api.planningcenteronline.com/services/v2/service_types/{service_type_id}/plans?filter=future"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=self._get_auth()) as response:
                if response.status != 200:
                    logger.error(f"PCO API error on get_upcoming_plans: status code {response.status}")
                    return []
                data = await response.json()
                plans = []
                for item in data.get("data", []):
                    attrs = item.get("attributes", {})
                    plans.append({
                        "id": item.get("id"),
                        "title": attrs.get("title") or attrs.get("dates", "Unknown Date"),
                        "date": attrs.get("sort_date", ""),
                        "teams": []
                    })
                return plans

    async def get_plan_items(self, service_type_id: str, plan_id: str) -> List[str]:
        if self.is_mock:
            return []
            
        url = f"https://api.planningcenteronline.com/services/v2/service_types/{service_type_id}/plans/{plan_id}/items?per_page=100"
        items = []
        async with aiohttp.ClientSession() as session:
            next_url = url
            while next_url:
                async with session.get(next_url, auth=self._get_auth()) as response:
                    if response.status != 200:
                        logger.error(f"PCO API error on get_plan_items: status code {response.status}")
                        break
                    data = await response.json()
                    for item in data.get("data", []):
                        title = item.get("attributes", {}).get("title")
                        if title:
                            items.append(title)
                    next_url = data.get("links", {}).get("next")
        return items

    async def get_plan_times(self, service_type_id: str, plan_id: str) -> Dict[str, str]:
        if self.is_mock:
            return {}
            
        url = f"https://api.planningcenteronline.com/services/v2/service_types/{service_type_id}/plans/{plan_id}/plan_times?per_page=100"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=self._get_auth()) as response:
                if response.status != 200:
                    return {}
                data = await response.json()
                
                times_map = {}
                for item in data.get("data", []):
                    attrs = item.get("attributes", {})
                    # Format time as 'Saturday 5:00 PM' etc
                    from datetime import datetime
                    import zoneinfo
                    dt_str = attrs.get("starts_at")
                    if dt_str:
                        # PCO returns ISO format e.g. 2026-07-18T22:00:00Z
                        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                        # Convert to central time (or local time)
                        local_tz = zoneinfo.ZoneInfo("America/Chicago")
                        dt_local = dt.astimezone(local_tz)
                        # Format example: 'Sat 5:00 PM'
                        formatted = dt_local.strftime('%a %I:%M %p').lstrip('0').replace(' 0', ' ')
                        times_map[item["id"]] = formatted
                    else:
                        times_map[item["id"]] = "Unknown Time"
                return times_map

    async def get_plan_team_members(self, service_type_id: str, plan_id: str) -> List[Dict[str, Any]]:
        if self.is_mock:
            return []
            
        url = f"https://api.planningcenteronline.com/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members?include=team&per_page=100"
        members = []
        teams_map = {}

        async with aiohttp.ClientSession() as session:
            next_url = url
            while next_url:
                async with session.get(next_url, auth=self._get_auth()) as response:
                    if response.status != 200:
                        logger.error(f"PCO API error on get_plan_team_members: status code {response.status}")
                        break
                    data = await response.json()
                    
                    # Build team map from included data
                    for inc in data.get("included", []):
                        if inc.get("type") == "Team":
                            teams_map[inc.get("id")] = inc.get("attributes", {}).get("name", "Unknown Team")
                            
                    for item in data.get("data", []):
                        attrs = item.get("attributes", {})
                        rel = item.get("relationships", {})
                        team_id = rel.get("team", {}).get("data", {}).get("id")
                        team_name = teams_map.get(team_id, "Unknown Team")
                        
                        time_ids = [t.get("id") for t in rel.get("service_times", {}).get("data", [])]
                        
                        members.append({
                            "id": item.get("id"),
                            "name": attrs.get("name", "Unknown Person"),
                            "position": attrs.get("team_position_name", "Unknown Position"),
                            "status": attrs.get("status", "U"),
                            "team_name": team_name,
                            "time_ids": time_ids
                        })
                    
                    next_url = data.get("links", {}).get("next")
        return members

    async def update_roster_status(self, service_type_id: str, plan_id: str, team_member_id: str, status: str) -> bool:
        if self.is_mock:
            return True
        
        url = f"https://api.planningcenteronline.com/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members/{team_member_id}"
        payload = {
            "data": {
                "type": "PlanPerson",
                "attributes": {
                    "status": status
                }
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, json=payload, auth=self._get_auth()) as response:
                if response.status in (200, 204):
                    return True
                logger.error(f"Failed to update roster status: {response.status} {await response.text()}")
                return False

    async def trigger_autoschedule(self, plan_id: str, team_id: str) -> List[Person]:
        if self.is_mock:
            return []
        return []

    async def get_needed_positions(self, service_type_id: str, plan_id: str) -> List[Dict[str, Any]]:
        if self.is_mock:
            return []
            
        url = f"https://api.planningcenteronline.com/services/v2/service_types/{service_type_id}/plans/{plan_id}/needed_positions?include=team,team_position&per_page=100"
        needed = []
        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=self._get_auth()) as response:
                if response.status != 200:
                    logger.error(f"PCO API error on get_needed_positions: {response.status}")
                    return []
                data = await response.json()
                
                included = data.get("included", [])
                team_map = {item["id"]: item["attributes"].get("name", "Unknown Team") for item in included if item["type"] == "Team"}
                pos_map = {item["id"]: item["attributes"].get("name", "Unknown Position") for item in included if item["type"] == "TeamPosition"}
                
                for item in data.get("data", []):
                    attrs = item.get("attributes", {})
                    rels = item.get("relationships", {})
                    
                    team_rel = rels.get("team") or {}
                    team_id = (team_rel.get("data") or {}).get("id")
                    
                    pos_rel = rels.get("team_position") or {}
                    pos_id = (pos_rel.get("data") or {}).get("id")
                    
                    time_rel = rels.get("time") or {}
                    time_id = (time_rel.get("data") or {}).get("id")
                    
                    team_name = team_map.get(team_id, "Unknown Team")
                    pos_name = pos_map.get(pos_id, "Unknown Position")
                    quantity = attrs.get("quantity", 1)
                    
                    needed.append({
                        "team_name": team_name,
                        "position_name": pos_name,
                        "quantity": quantity,
                        "time_id": time_id
                    })
        return needed

    async def get_plan_items_detailed(self, service_type_id: str, plan_id: str) -> List[Dict[str, Any]]:
        if self.is_mock:
            return [
                {"id": "item-1", "title": "Welcome & Announcements", "item_type": "header", "song_id": None},
                {"id": "item-2", "title": "Song", "item_type": "item", "song_id": None},
                {"id": "item-3", "title": "Way Maker", "item_type": "song", "song_id": "song-101", "arrangement_id": "arr-1"},
                {"id": "item-4", "title": "Great Are You Lord", "item_type": "song", "song_id": "song-102", "arrangement_id": "arr-2"},
                {"id": "item-5", "title": "Special Song Performance", "item_type": "item", "song_id": None},
            ]

        url = f"https://api.planningcenteronline.com/services/v2/service_types/{service_type_id}/plans/{plan_id}/items?include=song,arrangement&per_page=100"
        items = []
        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=self._get_auth()) as response:
                if response.status != 200:
                    logger.error(f"PCO API error on get_plan_items_detailed: {response.status}")
                    return []
                data = await response.json()
                for item in data.get("data", []):
                    attrs = item.get("attributes", {})
                    rels = item.get("relationships", {})
                    
                    song_rel = rels.get("song") or {}
                    song_id = (song_rel.get("data") or {}).get("id")
                    
                    arr_rel = rels.get("arrangement") or {}
                    arr_id = (arr_rel.get("data") or {}).get("id")
                    
                    items.append({
                        "id": item.get("id"),
                        "title": attrs.get("title", ""),
                        "item_type": attrs.get("item_type", "item"),
                        "song_id": song_id,
                        "arrangement_id": arr_id
                    })
        return items

    async def get_song_details(self, song_id: str) -> Dict[str, Any]:
        if self.is_mock:
            if song_id == "song-102":
                return {
                    "id": "song-102",
                    "title": "Great Are You Lord",
                    "artist": "All Sons & Daughters",
                    "youtube_url": None, # Missing YouTube link for mock testing
                    "lyrics_pdf_url": "https://api.planningcenteronline.com/mock/lyrics_great_are_you_lord.pdf",
                    "chords_pdf_url": "https://api.planningcenteronline.com/mock/chords_great_are_you_lord.pdf",
                    "arrangement_id": "arr-2"
                }
            return {
                "id": song_id,
                "title": "Way Maker",
                "artist": "Sinach",
                "youtube_url": "https://www.youtube.com/watch?v=iJCV_2H9xD0",
                "lyrics_pdf_url": "https://api.planningcenteronline.com/mock/lyrics_way_maker.pdf",
                "chords_pdf_url": "https://api.planningcenteronline.com/mock/chords_way_maker.pdf",
                "arrangement_id": "arr-1"
            }

        url = f"https://api.planningcenteronline.com/services/v2/songs/{song_id}?include=arrangements,attachments"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=self._get_auth()) as response:
                if response.status != 200:
                    logger.error(f"PCO API error on get_song_details for {song_id}: {response.status}")
                    return {"id": song_id, "title": "Unknown Title", "artist": "Unknown Artist", "youtube_url": None, "lyrics_pdf_url": None, "chords_pdf_url": None}
                
                data = await response.json()
                attrs = data.get("data", {}).get("attributes", {})
                title = attrs.get("title", "Unknown Title")
                artist = attrs.get("author", attrs.get("copyright", "Unknown Artist"))
                
                youtube_url = None
                lyrics_pdf_url = None
                chords_pdf_url = None
                arrangement_id = None
                
                included = data.get("included", [])
                for inc in included:
                    inc_type = inc.get("type")
                    inc_attrs = inc.get("attributes", {})
                    
                    if inc_type == "Arrangement":
                        if not arrangement_id:
                            arrangement_id = inc.get("id")
                        yt_id = inc_attrs.get("youtube_video_id")
                        if yt_id and not youtube_url:
                            youtube_url = f"https://www.youtube.com/watch?v={yt_id}"
                            
                    elif inc_type == "Attachment":
                        name = (inc_attrs.get("name") or "").lower()
                        filename = (inc_attrs.get("filename") or "").lower()
                        url_val = inc_attrs.get("url") or inc_attrs.get("web_url")
                        
                        if url_val and ("youtube.com" in url_val or "youtu.be" in url_val) and not youtube_url:
                            youtube_url = url_val
                        elif "lyric" in name or "lyric" in filename or "word" in name:
                            lyrics_pdf_url = url_val
                        elif "chord" in name or "chord" in filename or "chart" in name or "lead" in name:
                            chords_pdf_url = url_val
                        elif (filename.endswith(".pdf") or name.endswith(".pdf")) and not lyrics_pdf_url and not chords_pdf_url:
                            lyrics_pdf_url = url_val

                return {
                    "id": song_id,
                    "title": title,
                    "artist": artist,
                    "youtube_url": youtube_url,
                    "lyrics_pdf_url": lyrics_pdf_url,
                    "chords_pdf_url": chords_pdf_url,
                    "arrangement_id": arrangement_id
                }

    async def search_youtube(self, artist: str, title: str) -> Optional[str]:
        """Search YouTube for a matching song video URL."""
        if self.is_mock:
            safe_query = f"{artist}+{title}".replace(" ", "+")
            return f"https://www.youtube.com/watch?v=mock_{safe_query}"

        search_query = f"{artist} {title} official audio".strip()
        encoded_query = aiohttp.helpers.quote(search_query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        # Extract video ID from HTML source
                        import re
                        match = re.search(r'\"videoId\":\"([a-zA-Z0-9_-]{11})\"', html)
                        if match:
                            vid = match.group(1)
                            return f"https://www.youtube.com/watch?v={vid}"
        except Exception as e:
            logger.error(f"Error searching YouTube for {search_query}: {e}")
            
        # Fallback to direct search URL link
        return f"https://www.youtube.com/results?search_query={encoded_query}"

    async def add_youtube_link_to_song(self, song_id: str, youtube_url: str, arrangement_id: Optional[str] = None) -> bool:
        if self.is_mock:
            logger.info(f"PCO MOCK: Added YouTube link {youtube_url} to song {song_id}")
            return True

        url = f"https://api.planningcenteronline.com/services/v2/songs/{song_id}/attachments"
        payload = {
            "data": {
                "type": "Attachment",
                "attributes": {
                    "name": "YouTube Video",
                    "url": youtube_url
                }
            }
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, auth=self._get_auth()) as response:
                if response.status in (200, 201):
                    logger.info(f"Successfully attached YouTube link to song {song_id}")
                    return True
                logger.error(f"Failed to attach YouTube link to song {song_id}: status {response.status}")
                return False

