from dataclasses import dataclass
from typing import Optional

@dataclass
class Song:
    id: str
    title: str
    artist: str
    youtube_url: Optional[str] = None
    lyrics_pdf_url: Optional[str] = None
    chords_pdf_url: Optional[str] = None
    arrangement_id: Optional[str] = None
