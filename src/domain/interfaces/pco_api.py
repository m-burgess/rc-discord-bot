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

    async def get_plan_items(self, service_type_id: str, plan_id: str) -> List[str]:
        """Fetch service items (run-sheet) for a plan."""
        ...

    async def get_plan_times(self, service_type_id: str, plan_id: str) -> Dict[str, str]:
        """Fetch plan times (e.g. Sat 5:00 PM) for a plan."""
        ...

    async def get_plan_team_members(self, service_type_id: str, plan_id: str) -> List[Dict[str, Any]]:
        """Fetch detailed team rosters for a plan."""
        ...

    async def update_roster_status(self, plan_id: str, person_id: str, status: str) -> bool:
        """Update person status (e.g. Confirmed/Declined)."""
        ...

    async def trigger_autoschedule(self, plan_id: str, team_id: str) -> List[Person]:
        """Auto-schedule members for unfilled slots and return new roster."""
        ...

    async def get_needed_positions(self, service_type_id: str, plan_id: str) -> List[Dict[str, Any]]:
        """Fetch needed positions for a plan."""
        ...

    async def get_plan_items_detailed(self, service_type_id: str, plan_id: str) -> List[Dict[str, Any]]:
        """Fetch detailed plan items including linked song/arrangement IDs."""
        ...

    async def get_song_details(self, song_id: str) -> Dict[str, Any]:
        """Fetch details for a specific song including artist, title, links, and PDFs."""
        ...

    async def add_youtube_link_to_song(self, song_id: str, youtube_url: str, arrangement_id: Optional[str] = None) -> bool:
        """Add a YouTube link to a song or arrangement in Planning Center."""
        ...

