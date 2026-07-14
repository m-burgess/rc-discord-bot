from dataclasses import dataclass
from datetime import datetime

@dataclass
class Headcount:
    sanctuary_count: int
    overflow_count: int
    volunteer_count: int
    updated_at: datetime

@dataclass
class SeatingState:
    row_id: str
    seat_id: str
    is_occupied: bool
    updated_at: datetime
