import logging
import os
from src.infrastructure.storage.state_manager import SQLiteStateManager

LOG_FILE = "rc_bot_system.log"

def setup_logger():
    # Setup base configuration
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # File Handler
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console/Stream Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logging.info("System logger initialized successfully.")

# Custom error reporting helper that writes to database
class DatabaseLogger:
    def __init__(self, db_manager: SQLiteStateManager):
        self.db = db_manager

    def log_command_error(self, command_name: str, user_id: str, guild_id: str, error_trace: str):
        logging.error(f"Command '{command_name}' failed for User {user_id} in Guild {guild_id}: {error_trace}")
        try:
            self.db.log_error(command_name, str(user_id), str(guild_id), error_trace)
        except Exception as e:
            logging.critical(f"Failed to write command error to SQLite database: {e}")
