import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List

from core.dependencies import get_db, get_current_user
from db.models import Meeting, Question, MeetingStatus
from schemas.question import QuestionCreate, QuestionResponse, QuestionWithAnswer, CoachingResponse
from services.qa import qa_service

router = APIRouter()


@router.post("/{meeting_id}/questions", response_model=QuestionWithAnswer)
async def ask_question(
    meeting_id: int,
    question_data: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Ask a question about a meeting in an interactive chat session.
    Provides RAG-grounded answer, speaker statements ('user say'),
    Grok/Groq LLM reasoning trace, and suggestions on what to change in the talk.
    Caches previously answered questions to strictly limit LLM API calls.
    """
    user_id = current_user.get("user_id")
    
    # Verify meeting exists and belongs to user
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id,
        Meeting.user_id == user_id
    ).first()
    
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found"
        )
    
    if meeting.status != MeetingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Meeting is not ready for questions. Current status: {meeting.status.value}"
        )

    # 1. Strictly limit LLM API calls: Check if this exact question was already answered
    normalized_q = question_data.question_text.strip().lower()
    if not getattr(question_data, "force_refresh", False):
        existing_question = db.query(Question).filter(
            Question.meeting_id == meeting_id,
            func.lower(Question.question_text) == normalized_q
        ).order_by(Question.id.desc()).first()

        if (
            existing_question 
            and existing_question.answer_text 
            and not existing_question.answer_text.startswith("The meeting discussion")
        ):
            relevant_segs = []
            if existing_question.relevant_segments:
                try:
                    relevant_segs = json.loads(existing_question.relevant_segments)
                except Exception:
                    relevant_segs = []

            timestamps = []
            for s in (relevant_segs or []):
                if isinstance(s, dict):
                    timestamps.append({
                        "start_time": s.get("start_time", 0.0),
                        "end_time": s.get("end_time", 0.0),
                        "text": s.get("text", "")[:120]
                    })

            return QuestionWithAnswer(
                question=existing_question.question_text,
                answer=existing_question.answer_text,
                answer_text=existing_question.answer_text,
                reasoning=existing_question.reasoning or "Retrieved from cached meeting analysis.",
                user_say=existing_question.user_say or "",
                talk_improvements=[
                    "Ensure key decisions and action items are confirmed before ending the topic.",
                    "Encourage clear documentation of requirements and responsibilities."
                ],
                relevant_segments=relevant_segs,
                meeting_id=meeting_id,
                timestamps=timestamps,
                confidence=existing_question.confidence_score or 0.9,
                model_used="cache:fast-reply",
            )
    
    # Get answer from RAG QA service powered by Grok/Groq LLM
    result = await qa_service.answer_question_async(
        meeting_id=meeting_id,
        question=question_data.question_text,
        meeting_title=meeting.title,
        meeting_description=meeting.description,
        duration=meeting.duration,
        full_transcript=meeting.transcript,
        history=question_data.history,
    )
    
    # Prepare segment IDs or summaries for persistence
    relevant_segments_json = None
    if result.get("relevant_segments"):
        try:
            relevant_segments_json = json.dumps(result["relevant_segments"])
        except Exception:
            relevant_segments_json = str(result["relevant_segments"])

    # Save question, answer, reasoning, and user say to database
    db_question = Question(
        meeting_id=meeting_id,
        question_text=question_data.question_text,
        answer_text=result["answer"],
        reasoning=result.get("reasoning"),
        user_say=result.get("user_say"),
        relevant_segments=relevant_segments_json,
        confidence_score=result.get("confidence"),
    )
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    
    # Format response
    response = QuestionWithAnswer(
        question=question_data.question_text,
        answer=result["answer"],
        answer_text=result["answer"],
        reasoning=result.get("reasoning"),
        user_say=result.get("user_say"),
        talk_improvements=result.get("talk_improvements", []),
        relevant_segments=result.get("relevant_segments", []),
        meeting_id=meeting_id,
        timestamps=result.get("timestamps", []),
        confidence=result.get("confidence"),
        model_used=result.get("model_used"),
    )
    
    return response


@router.post("/{meeting_id}/coaching", response_model=CoachingResponse)
async def get_meeting_coaching(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Generate an executive conversation coaching review of the meeting:
    Critiques communication dynamics and outlines what should be changed in the talk.
    """
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

    if meeting.status != MeetingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Meeting is not completed yet. Status: {meeting.status.value}"
        )

    coaching = await qa_service.get_conversation_coaching(
        meeting_id=meeting.id,
        meeting_title=meeting.title,
        full_transcript=meeting.transcript,
    )

    return CoachingResponse(
        meeting_id=meeting_id,
        title=meeting.title,
        assessment=coaching.get("answer", "Analysis of meeting dynamics."),
        user_say=coaching.get("user_say", ""),
        reasoning=coaching.get("reasoning", ""),
        talk_improvements=coaching.get("talk_improvements", []),
        model_used=coaching.get("model_used"),
    )


@router.get("/{meeting_id}/questions", response_model=List[QuestionResponse])
def list_questions(
    meeting_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List all questions and answers (with reasoning and user say) for a meeting."""
    user_id = current_user.get("user_id")

    # Verify meeting exists and belongs to user
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id,
        Meeting.user_id == user_id
    ).first()
    
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found"
        )
    
    questions = db.query(Question).filter(
        Question.meeting_id == meeting_id
    ).order_by(Question.created_at.desc()).offset(skip).limit(limit).all()
    
    return questions
