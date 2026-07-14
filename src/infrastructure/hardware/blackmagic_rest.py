import aiohttp
import logging
from src.domain.entities.broadcast import CameraState

logger = logging.getLogger(__name__)

class BlackmagicRESTClient:
    def __init__(self, ip: str):
        self.ip = ip
        self.is_mock = (ip == "127.0.0.1" or not ip)
        self._recording = False

    async def set_recording(self, camera_id: str, record: bool) -> bool:
        logger.info(f"Blackmagic REST: Camera {camera_id} set recording to {record}")
        self._recording = record
        if self.is_mock:
            return True

        url = f"http://{self.ip}/control/api/v1/transports/0/record"
        payload = {"record": record}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=5.0) as response:
                    if response.status == 200:
                        return True
                    logger.error(f"Blackmagic camera API returned code {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Blackmagic API: Exception triggering record command: {e}")
            return False

    async def get_camera_status(self, camera_id: str) -> CameraState:
        return CameraState(
            recording=self._recording,
            camera_id=camera_id,
            transport_status="recording" if self._recording else "stopped"
        )
