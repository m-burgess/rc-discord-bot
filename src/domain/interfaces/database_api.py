from typing import Protocol, List, Dict, Any, Optional
from datetime import datetime
from src.domain.entities.headcount import Headcount, SeatingState

class DatabaseAPI(Protocol):
    def initialize_db(self) -> None:
        """Initialize the database tables."""
        ...

    def get_headcount(self) -> Headcount:
        """Get the latest attendance headcount counts."""
        ...

    def increment_count(self, zone: str, value: int) -> Headcount:
        """Increment count for zone (sanctuary, overflow, volunteer) transactionally."""
        ...

    def reset_counts(self) -> Headcount:
        """Reset all counts back to zero."""
        ...

    def get_seating_map(self) -> List[SeatingState]:
        """Fetch all seating state rows."""
        ...

    def update_seat(self, row_id: str, seat_id: str, is_occupied: bool) -> bool:
        """Update occupancy of a specific seat."""
        ...

    def log_error(self, command_name: str, user_id: str, guild_id: str, traceback_str: str) -> None:
        """Store command runtime crash errors for FTS and analytics."""
        ...

    def search_errors(self, query: str) -> List[Dict[str, Any]]:
        """Search logged errors using FTS or string matching."""
        ...
