from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Person:
    id: str
    first_name: str
    last_name: str
    discord_id: Optional[str] = None

@dataclass
class CheckIn:
    id: str
    person: Person
    checked_in_at: datetime
    checked_out_at: Optional[datetime] = None
    location: str = ""
    status: str = "active"  # "active" or "checked_out"
