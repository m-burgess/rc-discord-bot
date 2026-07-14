from typing import Protocol
from src.domain.entities.broadcast import ATEMState, CameraState

class HardwareAPI(Protocol):
    async def connect(self) -> bool:
        """Establish connections to hardware controllers."""
        ...

    async def disconnect(self) -> None:
        """Disconnect safely from all devices."""
        ...

    async def recall_wing_snapshot(self, snapshot_id: int) -> bool:
        """Recall a console snapshot on the Behringer WING using OSC."""
        ...

    async def set_atem_on_air(self, on_air: bool) -> bool:
        """Set ATEM Mini switcher to On Air or Off Air."""
        ...

    async def set_atem_program_input(self, input_id: int) -> bool:
        """Change the active program input on ATEM switcher."""
        ...

    async def set_camera_recording(self, camera_id: str, record: bool) -> bool:
        """Start or stop recording on the Studio Camera via REST API."""
        ...

    async def get_atem_state(self) -> ATEMState:
        """Fetch the current state of the ATEM switcher."""
        ...

    async def get_camera_state(self, camera_id: str) -> CameraState:
        """Fetch status of a Studio Camera."""
        ...
