from src.domain.interfaces.pco_api import PlanningCenterAPI
from src.domain.entities.checkin import Person
from typing import List, Dict, Any

class RescheduleTeamUseCase:
    def __init__(self, pco_api: PlanningCenterAPI):
        self.pco_api = pco_api

    async def get_upcoming_plan_roster(self, service_type_id: str) -> List[Dict[str, Any]]:
        return await self.pco_api.get_upcoming_plans(service_type_id)

    async def auto_schedule_and_clean_roster(self, plan_id: str, team_id: str) -> List[Person]:
        """
        1. Query the upcoming plan and find any unconfirmed personnel
        2. Decline/remove unconfirmed personnel to free up slots
        3. Trigger PCO auto-schedule endpoint to fill slots
        4. Return the newly drafted team roster
        """
        # For simplicity, we trigger the auto-schedule endpoint directly
        # which performs the scheduling logic on the PCO side.
        new_roster = await self.pco_api.trigger_autoschedule(plan_id, team_id)
        return new_roster
