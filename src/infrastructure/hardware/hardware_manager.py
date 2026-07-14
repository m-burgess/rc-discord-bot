from src.domain.interfaces.hardware_api import HardwareAPI
from src.domain.entities.broadcast import ATEMState, CameraState
from src.infrastructure.hardware.behringer_osc import BehringerOSCClient
from src.infrastructure.hardware.atem_network import ATEMNetworkClient
from src.infrastructure.hardware.blackmagic_rest import BlackmagicRESTClient

class HardwareManager(HardwareAPI):
    def __init__(self, wing_ip: str, wing_port: int, atem_ip: str, camera_ip: str):
        self.wing = BehringerOSCClient(wing_ip, wing_port)
        self.atem = ATEMNetworkClient(atem_ip)
        self.camera = BlackmagicRESTClient(camera_ip)

    async def connect(self) -> bool:
        wing_ok = self.wing.connect()
        atem_ok = self.atem.connect()
        return wing_ok and atem_ok

    async def disconnect(self) -> None:
        self.wing.disconnect()
        self.atem.disconnect()

    async def recall_wing_snapshot(self, snapshot_id: int) -> bool:
        return await self.wing.recall_snapshot(snapshot_id)

    async def set_atem_on_air(self, on_air: bool) -> bool:
        return await self.atem.set_on_air(on_air)

    async def set_atem_program_input(self, input_id: int) -> bool:
        return await self.atem.set_program_input(input_id)

    async def set_camera_recording(self, camera_id: str, record: bool) -> bool:
        return await self.camera.set_recording(camera_id, record)

    async def get_atem_state(self) -> ATEMState:
        return await self.atem.get_state()

    async def get_camera_state(self, camera_id: str) -> CameraState:
        return await self.camera.get_camera_status(camera_id)
