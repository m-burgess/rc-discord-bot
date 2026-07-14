from src.domain.interfaces.database_api import DatabaseAPI
from src.domain.entities.headcount import Headcount, SeatingState
from typing import List

class CalculateCountsUseCase:
    def __init__(self, db_api: DatabaseAPI):
        self.db_api = db_api

    def increment_zone_count(self, zone: str, value: int = 1) -> Headcount:
        if zone not in ("sanctuary", "overflow", "volunteer"):
            raise ValueError(f"Invalid headcount zone: {zone}")
        return self.db_api.increment_count(zone, value)

    def get_current_headcount(self) -> Headcount:
        return self.db_api.get_headcount()

    def reset_headcount(self) -> Headcount:
        return self.db_api.reset_counts()

    def update_seating(self, row_id: str, seat_id: str, is_occupied: bool) -> bool:
        return self.db_api.update_seat(row_id, seat_id, is_occupied)

    def get_seating_state(self) -> List[SeatingState]:
        return self.db_api.get_seating_map()
