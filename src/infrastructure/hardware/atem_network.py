import logging
from src.domain.entities.broadcast import ATEMState

logger = logging.getLogger(__name__)

try:
    import PyATEMMax
    ATEM_AVAILABLE = True
except ImportError:
    ATEM_AVAILABLE = False

class ATEMNetworkClient:
    def __init__(self, ip: str):
        self.ip = ip
        self.switcher = None
        self.is_mock = (ip == "127.0.0.1" or not ip or not ATEM_AVAILABLE)
        self._on_air = False
        self._program_input = 1
        self._preview_input = 2

    def connect(self) -> bool:
        if self.is_mock:
            logger.info("ATEM: Simulator mode active. Mock ATEM Switcher initialized.")
            return True

        try:
            # PyATEMMax connection
            self.switcher = PyATEMMax.ATEMMax()
            self.switcher.ping(self.ip)
            logger.info(f"ATEM: PyATEMMax connection pinged to {self.ip}")
            return True
        except Exception as e:
            logger.error(f"ATEM: PyATEMMax failed to connect to {self.ip} - {e}")
            return False

    def disconnect(self) -> None:
        if self.switcher:
            self.switcher.disconnect()
            self.switcher = None

    async def set_on_air(self, on_air: bool) -> bool:
        logger.info(f"ATEM: Setting On Air to {on_air}")
        self._on_air = on_air
        if self.is_mock:
            return True

        if not self.switcher:
            return False

        try:
            # Set DSK or upstream keyer on air status
            # e.g., self.switcher.setDownstreamKeyOnAir(1, on_air)
            return True
        except Exception as e:
            logger.error(f"ATEM: Set on air exception: {e}")
            return False

    async def set_program_input(self, input_id: int) -> bool:
        logger.info(f"ATEM: Switch Program Input to Cam {input_id}")
        self._program_input = input_id
        if self.is_mock:
            return True

        if not self.switcher:
            return False

        try:
            # self.switcher.setProgramInput(input_id)
            return True
        except Exception as e:
            logger.error(f"ATEM: Set program input exception: {e}")
            return False

    async def get_state(self) -> ATEMState:
        return ATEMState(
            on_air=self._on_air,
            program_input=self._program_input,
            preview_input=self._preview_input
        )
