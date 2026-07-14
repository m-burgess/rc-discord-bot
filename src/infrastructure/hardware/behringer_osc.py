import logging
from pythonosc.udp_client import SimpleUDPClient

logger = logging.getLogger(__name__)

class BehringerOSCClient:
    def __init__(self, ip: str, port: int):
        self.ip = ip
        self.port = port
        self.client = None
        self.is_mock = (ip == "127.0.0.1" or not ip)

    def connect(self) -> bool:
        if self.is_mock:
            logger.info("OSC: Simulator mode active. Mock Behringer WING initialized.")
            return True
        try:
            self.client = SimpleUDPClient(self.ip, self.port)
            logger.info(f"OSC: SimpleUDPClient bound to {self.ip}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"OSC: Connection failed to WING on {self.ip}:{self.port} - {e}")
            return False

    def disconnect(self) -> None:
        self.client = None

    async def recall_snapshot(self, snapshot_id: int) -> bool:
        logger.info(f"OSC: Sending snapshot recall code for index {snapshot_id}")
        if self.is_mock:
            return True
        
        if not self.client:
            logger.warning("OSC Client not connected.")
            return False

        try:
            # WING OSC snapshot trigger command
            # Typically follows: /action/recall-snapshot index
            self.client.send_message("/action/recall-snapshot", snapshot_id)
            return True
        except Exception as e:
            logger.error(f"OSC: Failed to send UDP snapshot recall: {e}")
            return False
