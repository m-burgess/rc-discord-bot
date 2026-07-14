from src.domain.interfaces.pco_api import PlanningCenterAPI
from src.domain.entities.checkin import CheckIn
from typing import List

class ProcessCheckInUseCase:
    def __init__(self, pco_api: PlanningCenterAPI):
        self.pco_api = pco_api

    async def get_active_checkins(self, date_str: str) -> List[CheckIn]:
        checkins = await self.pco_api.get_checkins(date_str)
        return [c for c in checkins if c.status == "active"]

    async def execute_checkin(self, person_id: str, location_id: str) -> bool:
        return await self.pco_api.check_in_person(person_id, location_id)

    async def execute_checkout(self, checkin_id: str) -> bool:
        return await self.pco_api.check_out_person(checkin_id)
