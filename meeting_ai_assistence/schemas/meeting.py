from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from db.models import MeetingStatus


class TranscriptSegmentBase(BaseModel):
    text: str
    start_time: float
    end_time: float


class TranscriptSegmentResponse(TranscriptSegmentBase):
    id: int
    chunk_index: Optional[int] = None
    
    class Config:
        from_attributes = True


class MeetingBase(BaseModel):
    title: str
    description: Optional[str] = None


class MeetingCreate(MeetingBase):
    pass


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class MeetingResponse(MeetingBase):
    id: int
    audio_file_path: str
    duration: Optional[float] = None
    status: MeetingStatus
    transcript: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    user_id: int
    
    class Config:
        from_attributes = True


class MeetingWithSegments(MeetingResponse):
    transcript_segments: List[TranscriptSegmentResponse] = []
