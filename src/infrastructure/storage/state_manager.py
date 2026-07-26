import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any
from src.domain.interfaces.database_api import DatabaseAPI
from src.domain.entities.headcount import Headcount, SeatingState

DB_PATH = "rc_bot_data.db"

class SQLiteStateManager(DatabaseAPI):
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.initialize_db()

    def _get_connection(self) -> sqlite3.Connection:
        # SQLite connection config for safety
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize_db(self) -> None:
        with self._get_connection() as conn:
            # Create headcounts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS headcounts (
                    id INTEGER PRIMARY KEY CHECK (id = 1), -- Ensure single row
                    sanctuary_count INTEGER DEFAULT 0,
                    overflow_count INTEGER DEFAULT 0,
                    volunteer_count INTEGER DEFAULT 0,
                    updated_at TEXT
                )
            """)
            # Initialize single row if not exists
            conn.execute("""
                INSERT OR IGNORE INTO headcounts (id, sanctuary_count, overflow_count, volunteer_count, updated_at)
                VALUES (1, 0, 0, 0, ?)
            """, (datetime.utcnow().isoformat(),))

            # Create seating map table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seating_map (
                    row_id TEXT,
                    seat_id TEXT,
                    is_occupied INTEGER DEFAULT 0,
                    updated_at TEXT,
                    PRIMARY KEY (row_id, seat_id)
                )
            """)

            # Populate initial mock seats if table is empty
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM seating_map")
            if cursor.fetchone()[0] == 0:
                # Seed a small 10x10 seating grid for illustration/testing
                for r in range(1, 11):
                    for s in range(1, 11):
                        cursor.execute("""
                            INSERT INTO seating_map (row_id, seat_id, is_occupied, updated_at)
                            VALUES (?, ?, 0, ?)
                        """, (f"Row-{r}", f"Seat-{s}", datetime.utcnow().isoformat()))

            # Create error logging table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS command_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    command_name TEXT,
                    user_id TEXT,
                    guild_id TEXT,
                    traceback_str TEXT
                )
            """)

            # Create virtual FTS5 table for command errors to allow fast searching
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS command_errors_fts USING fts5(
                        command_name,
                        traceback_str,
                        content='command_errors',
                        content_rowid='id'
                    )
                """)
                # Trigger to keep FTS index updated automatically
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS t_errors_ai AFTER INSERT ON command_errors BEGIN
                        INSERT INTO command_errors_fts(rowid, command_name, traceback_str)
                        VALUES (new.id, new.command_name, new.traceback_str);
                    END;
                """)
            except sqlite3.OperationalError:
                # Fallback if FTS5 is not compiled in this Python environment's sqlite3 binary
                pass

            # Create reminders table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    service_type_id TEXT NOT NULL,
                    day_of_week INTEGER NOT NULL,
                    hour INTEGER NOT NULL,
                    minute INTEGER NOT NULL
                )
            """)

            conn.commit()

    def get_headcount(self) -> Headcount:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT sanctuary_count, overflow_count, volunteer_count, updated_at FROM headcounts WHERE id = 1")
            row = cursor.fetchone()
            return Headcount(
                sanctuary_count=row["sanctuary_count"],
                overflow_count=row["overflow_count"],
                volunteer_count=row["volunteer_count"],
                updated_at=datetime.fromisoformat(row["updated_at"])
            )

    def increment_count(self, zone: str, value: int) -> Headcount:
        column_map = {
            "sanctuary": "sanctuary_count",
            "overflow": "overflow_count",
            "volunteer": "volunteer_count"
        }
        column = column_map[zone]
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Transactional update
            cursor.execute(f"""
                UPDATE headcounts
                SET {column} = MAX(0, {column} + ?), updated_at = ?
                WHERE id = 1
            """, (value, datetime.utcnow().isoformat()))
            conn.commit()
        return self.get_headcount()

    def reset_counts(self) -> Headcount:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE headcounts
                SET sanctuary_count = 0, overflow_count = 0, volunteer_count = 0, updated_at = ?
                WHERE id = 1
            """, (datetime.utcnow().isoformat(),))
            conn.commit()
        return self.get_headcount()

    def get_seating_map(self) -> List[SeatingState]:
        states = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT row_id, seat_id, is_occupied, updated_at FROM seating_map")
            for row in cursor.fetchall():
                states.append(SeatingState(
                    row_id=row["row_id"],
                    seat_id=row["seat_id"],
                    is_occupied=bool(row["is_occupied"]),
                    updated_at=datetime.fromisoformat(row["updated_at"])
                ))
        return states

    def update_seat(self, row_id: str, seat_id: str, is_occupied: bool) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE seating_map
                SET is_occupied = ?, updated_at = ?
                WHERE row_id = ? AND seat_id = ?
            """, (1 if is_occupied else 0, datetime.utcnow().isoformat(), row_id, seat_id))
            conn.commit()
            return cursor.rowcount > 0

    def log_error(self, command_name: str, user_id: str, guild_id: str, traceback_str: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO command_errors (timestamp, command_name, user_id, guild_id, traceback_str)
                VALUES (?, ?, ?, ?, ?)
            """, (datetime.utcnow().isoformat(), command_name, user_id, guild_id, traceback_str))
            conn.commit()

    def search_errors(self, query: str) -> List[Dict[str, Any]]:
        results = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Attempt to search using FTS5 virtual table
                cursor.execute("""
                    SELECT c.id, c.timestamp, c.command_name, c.user_id, c.guild_id, c.traceback_str
                    FROM command_errors c
                    JOIN command_errors_fts f ON f.rowid = c.id
                    WHERE command_errors_fts MATCH ?
                    ORDER BY c.timestamp DESC
                """, (query,))
            except sqlite3.OperationalError:
                # Fallback to standard LIKE if FTS5 fails or is unavailable
                cursor.execute("""
                    SELECT id, timestamp, command_name, user_id, guild_id, traceback_str
                    FROM command_errors
                    WHERE command_name LIKE ? OR traceback_str LIKE ?
                    ORDER BY timestamp DESC
                """, (f"%{query}%", f"%{query}%"))
            
            for row in cursor.fetchall():
                results.append(dict(row))
        return results

    def set_reminder(self, guild_id: str, service_type_id: str, day_of_week: int, hour: int, minute: int) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reminders (guild_id, service_type_id, day_of_week, hour, minute)
                VALUES (?, ?, ?, ?, ?)
            """, (guild_id, service_type_id, day_of_week, hour, minute))
            conn.commit()
            return cursor.lastrowid

    def get_all_reminders(self) -> List[Dict[str, Any]]:
        results = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, guild_id, service_type_id, day_of_week, hour, minute FROM reminders")
            for row in cursor.fetchall():
                results.append(dict(row))
        return results

    def delete_reminder(self, reminder_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            conn.commit()
            return cursor.rowcount > 0
