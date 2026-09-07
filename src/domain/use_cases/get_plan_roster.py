from src.domain.interfaces.pco_api import PlanningCenterAPI
from src.domain.entities.checkin import Person
from typing import List, Dict, Any

from datetime import datetime, timezone

class GetPlanRosterUseCase:
    def __init__(self, pco_api: PlanningCenterAPI):
        self.pco_api = pco_api

    async def get_upcoming_plan_roster(self, service_type_id: str) -> List[Dict[str, Any]]:
        plans = await self.pco_api.get_upcoming_plans(service_type_id)
        if not plans:
            return []
            
        # If we are past the plan's sort_date time, check the next plan instead
        try:
            plan_date_str = plans[0].get("date", "")
            if plan_date_str and len(plans) > 1:
                # Parse the ISO 8601 date (replace Z with +00:00 for python's fromisoformat)
                plan_dt = datetime.strptime(plan_date_str.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
                plan_dt = plan_dt.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                
                # If current time is past the plan time, pop the plan
                if now >= plan_dt:
                    plans.pop(0)
        except Exception as e:
            print(f"Error parsing date: {e}")
            
        first_plan = plans[0]
        plan_id = first_plan["id"]
        
        # Fetch detailed items and roster
        items = await self.pco_api.get_plan_items(service_type_id, plan_id)
        plan_times = await self.pco_api.get_plan_times(service_type_id, plan_id)
        members = await self.pco_api.get_plan_team_members(service_type_id, plan_id)
        needed_positions_list = await self.pco_api.get_needed_positions(service_type_id, plan_id)
        
        first_plan["items"] = items
        
        # Group needed positions by team
        needed_by_team = {}
        for np in needed_positions_list:
            team_name = np["team_name"]
            if team_name not in needed_by_team:
                needed_by_team[team_name] = []
            needed_by_team[team_name].append(np)
            
        first_plan["needed_positions"] = needed_by_team
        
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

