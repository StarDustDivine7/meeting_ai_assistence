from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from core.dependencies import get_db, get_current_user
from db.models import Meeting, TranscriptSegment, MeetingStatus, User
from schemas.meeting import MeetingCreate, MeetingResponse, MeetingUpdate, MeetingWithSegments
from services.storage import storage_service
from workers.meeting_processor import meeting_processor
from vector_store.faiss_store import FAISSStore

router = APIRouter()


@router.post("/", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Upload audio file and create a new meeting."""
    # Save audio file
    audio_path = await storage_service.save_audio_file(audio_file)
    
    # Create meeting record
    user_id = current_user.get("user_id")
    meeting = Meeting(
        title=title,
        description=description,
        audio_file_path=audio_path,
        status=MeetingStatus.UPLOADING,
        user_id=user_id
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    
    # Start background processing
    background_tasks.add_task(
        meeting_processor.process_meeting_sync,
        meeting.id
    )
    
    return meeting


@router.get("/", response_model=List[MeetingResponse])
def list_meetings(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List all meetings for the current user."""
    user_id = current_user.get("user_id")
    meetings = db.query(Meeting).filter(
        Meeting.user_id == user_id
    ).order_by(Meeting.created_at.desc()).offset(skip).limit(limit).all()
    
    return meetings


@router.get("/{meeting_id}", response_model=MeetingWithSegments)
def get_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific meeting with transcript segments."""
    user_id = current_user.get("user_id")
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id,
        Meeting.user_id == user_id
    ).first()
    
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found"
        )
    
    return meeting


@router.patch("/{meeting_id}", response_model=MeetingResponse)
def update_meeting(
    meeting_id: int,
    updates: MeetingUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a meeting's title and/or description for its owner."""
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id,
        Meeting.user_id == current_user.get("user_id"),
    ).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    changes = updates.model_dump(exclude_unset=True)
    if "title" in changes:
        title = (changes["title"] or "").strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Title cannot be empty")
        meeting.title = title
    if "description" in changes:
        meeting.description = changes["description"].strip() if changes["description"] else None

    db.commit()
    db.refresh(meeting)
    return meeting


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a meeting and its associated data."""
    user_id = current_user.get("user_id")
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id,
        Meeting.user_id == user_id
    ).first()
    
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found"
        )
    
    # Delete meeting and its related database records first. Then remove its
    # local audio and search index artifacts.
    audio_file_path = meeting.audio_file_path
    db.delete(meeting)
    db.commit()
    storage_service.delete_file(audio_file_path)
    FAISSStore.delete_meeting_index(meeting_id)

    return None


@router.get("/{meeting_id}/status", response_model=MeetingResponse)
def get_meeting_status(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get the processing status of a meeting."""
    user_id = current_user.get("user_id")
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id,
        Meeting.user_id == user_id
    ).first()
    
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found"
        )
    
    return meeting
