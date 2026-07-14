from typing import Protocol, List, Dict, Any, Optional
from src.domain.entities.checkin import CheckIn, Person

class PlanningCenterAPI(Protocol):
    async def get_checkins(self, date_str: str) -> List[CheckIn]:
        """Fetch check-ins for a specific date."""
        ...

    async def get_people_by_team(self, team_id: str) -> List[Person]:
        """Fetch team roster from PCO Services."""
        ...

    async def check_in_person(self, person_id: str, location_id: str) -> bool:
        """Create check-in on PCO Check-Ins."""
        ...

    async def check_out_person(self, checkin_id: str) -> bool:
        """Perform check-out on PCO Check-Ins."""
        ...

    async def get_upcoming_plans(self, service_type_id: str) -> List[Dict[str, Any]]:
        """Get upcoming plans for the service type."""
        ...

    async def update_roster_status(self, plan_id: str, person_id: str, status: str) -> bool:
        """Update person status (e.g. Confirmed/Declined)."""
        ...

    async def trigger_autoschedule(self, plan_id: str, team_id: str) -> List[Person]:
        """Auto-schedule members for unfilled slots and return new roster."""
        ...
