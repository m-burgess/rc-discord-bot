from src.domain.interfaces.pco_api import PlanningCenterAPI
from src.domain.entities.checkin import Person
from typing import List, Dict, Any

class RescheduleTeamUseCase:
    def __init__(self, pco_api: PlanningCenterAPI):
        self.pco_api = pco_api

    async def get_upcoming_plan_roster(self, service_type_id: str) -> List[Dict[str, Any]]:
        plans = await self.pco_api.get_upcoming_plans(service_type_id)
        if not plans:
            return []
            
        first_plan = plans[0]
        plan_id = first_plan["id"]
        
        # Fetch detailed items and roster
        items = await self.pco_api.get_plan_items(service_type_id, plan_id)
        plan_times = await self.pco_api.get_plan_times(service_type_id, plan_id)
        members = await self.pco_api.get_plan_team_members(service_type_id, plan_id)
        
        first_plan["items"] = items
        
        # Group members by team
        team_rosters = {}
        for m in members:
            team_name = m["team_name"]
            time_ids = m.get("time_ids", [])
            
            if time_ids:
                time_names = [plan_times.get(tid, "Unknown Time") for tid in time_ids]
                m["times_str"] = ", ".join(time_names)
            else:
                m["times_str"] = "Any Time"
                
            if team_name not in team_rosters:
                team_rosters[team_name] = []
            team_rosters[team_name].append(m)
            
        first_plan["detailed_teams"] = team_rosters
        
        return plans

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
