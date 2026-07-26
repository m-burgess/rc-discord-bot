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
            return []
            
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
                            "name": attrs.get("name", "Unknown Person"),
                            "position": attrs.get("team_position_name", "Unknown Position"),
                            "status": attrs.get("status", "U"),
                            "team_name": team_name,
                            "time_ids": time_ids
                        })
                    
                    next_url = data.get("links", {}).get("next")
        return members

    async def update_roster_status(self, plan_id: str, person_id: str, status: str) -> bool:
        if self.is_mock:
            return True
        return False

    async def trigger_autoschedule(self, plan_id: str, team_id: str) -> List[Person]:
        if self.is_mock:
            return []
        return []
