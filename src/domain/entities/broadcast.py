from dataclasses import dataclass
from typing import Optional

@dataclass
class OSCConsoleSnapshot:
    snapshot_index: int
    name: str
    description: Optional[str] = None

@dataclass
class ATEMState:
    on_air: bool
    program_input: int
    preview_input: int

@dataclass
class CameraState:
    recording: bool
    camera_id: str
    transport_status: str
