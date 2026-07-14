from src.domain.interfaces.hardware_api import HardwareAPI
import logging

logger = logging.getLogger(__name__)

class TriggerBroadcastUseCase:
    def __init__(self, hardware_api: HardwareAPI):
        self.hardware_api = hardware_api

    async def execute_start_broadcast(self, wing_snapshot_id: int = 1) -> bool:
        """Sequence to start a broadcast service."""
        try:
            # 1. Connect hardware clients
            connected = await self.hardware_api.connect()
            if not connected:
                logger.error("Failed to connect to hardware controllers during broadcast initiation.")
                return False

            # 2. Recall audio snapshot on Behringer WING
            wing_ok = await self.hardware_api.recall_wing_snapshot(wing_snapshot_id)
            if not wing_ok:
                logger.warning("Behringer WING OSC snapshot recall returned failure/timeout.")

            # 3. Set ATEM switcher state to On Air
            atem_ok = await self.hardware_api.set_atem_on_air(True)
            if not atem_ok:
                logger.warning("ATEM Switcher set_atem_on_air returned failure.")

            # 4. Trigger record on cameras
            cam_ok = await self.hardware_api.set_camera_recording("camera_1", True)
            if not cam_ok:
                logger.warning("Camera 1 recording command returned failure.")

            return True
        except Exception as e:
            logger.exception(f"Unexpected error in execute_start_broadcast: {e}")
            return False

    async def execute_stop_broadcast(self) -> bool:
        """Sequence to stop broadcast service."""
        try:
            connected = await self.hardware_api.connect()
            if not connected:
                return False

            await self.hardware_api.set_atem_on_air(False)
            await self.hardware_api.set_camera_recording("camera_1", False)
            return True
        except Exception as e:
            logger.exception(f"Unexpected error in execute_stop_broadcast: {e}")
            return False
