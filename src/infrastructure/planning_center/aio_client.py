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
            logger.info("PCO: returning mocked check-ins list.")
            return [
                CheckIn(
                    id="mock-ci-1",
                    person=Person(id="person-1", first_name="John", last_name="Doe", discord_id="1234567890"),
                    checked_in_at=datetime.utcnow(),
                    location="Sanctuary Main Lobby"
                ),
                CheckIn(
                    id="mock-ci-2",
                    person=Person(id="person-2", first_name="Jane", last_name="Smith", discord_id="0987654321"),
                    checked_in_at=datetime.utcnow(),
                    location="Children's Check-In"
                )
            ]

        url = f"https://api.planningcenteronline.com/check-ins/v2/check_ins?filter=date&date={date_str}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=self._get_auth()) as response:
                if response.status != 200:
                    logger.error(f"PCO API error: status code {response.status}")
                    return []
                data = await response.json()
                # Parse to entities...
                checkins = []
                for item in data.get("data", []):
                    # Simplified parsing
                    person_attribs = item.get("attributes", {})
                    checkins.append(
                        CheckIn(
                            id=item.get("id"),
                            person=Person(id="pco-p-id", first_name="PCO", last_name="User"),
                            checked_in_at=datetime.utcnow(),
                            location="Sanctuary"
                        )
                    )
                return checkins

    async def get_people_by_team(self, team_id: str) -> List[Person]:
        if self.is_mock:
            return [
                Person(id="vol-1", first_name="Aiden", last_name="Pastor", discord_id="111111"),
                Person(id="vol-2", first_name="Sarah", last_name="Singer", discord_id="222222")
            ]
        # Real PCO implementation...
        return []

    async def check_in_person(self, person_id: str, location_id: str) -> bool:
        if self.is_mock:
            logger.info(f"Mock Check-In successful for Person {person_id} at Location {location_id}.")
            return True
        return False

    async def check_out_person(self, checkin_id: str) -> bool:
        if self.is_mock:
            logger.info(f"Mock Check-Out successful for Checkin {checkin_id}.")
            return True
        return False

    async def get_upcoming_plans(self, service_type_id: str) -> List[Dict[str, Any]]:
        if self.is_mock:
            return [
                {
                    "id": "plan-101",
                    "title": "Sunday Worship Service",
                    "date": "2026-07-19",
                    "teams": [
                        {"id": "team-audio", "name": "Audio Visual Team", "status": "Confirmed"},
                        {"id": "team-host", "name": "Host Team", "status": "Unconfirmed"}
                    ]
                }
            ]
        return []

    async def update_roster_status(self, plan_id: str, person_id: str, status: str) -> bool:
        if self.is_mock:
            return True
        return False

    async def trigger_autoschedule(self, plan_id: str, team_id: str) -> List[Person]:
        if self.is_mock:
            logger.info(f"Mock Trigger Auto-schedule for Plan {plan_id}, Team {team_id}")
            return [
                Person(id="auto-vol-1", first_name="Robert", last_name="Reader", discord_id="333333"),
                Person(id="auto-vol-2", first_name="Emily", last_name="Editor", discord_id="444444")
            ]
        return []
