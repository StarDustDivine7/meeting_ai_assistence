from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


class QuestionCreate(BaseModel):
    question_text: str
    history: Optional[List[Dict[str, str]]] = None
    force_refresh: Optional[bool] = False


class QuestionResponse(BaseModel):
    id: int
    meeting_id: int
    question_text: str
    answer_text: str
    reasoning: Optional[str] = None
    user_say: Optional[str] = None
    talk_improvements: Optional[str] = None
    relevant_segments: Optional[str] = None
    confidence_score: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class QuestionWithAnswer(BaseModel):
    question: str
    answer: str
    answer_text: Optional[str] = None
    reasoning: Optional[str] = None
    user_say: Optional[str] = None
    talk_improvements: Optional[List[str]] = []
    relevant_segments: List[dict] = []
    meeting_id: int
    timestamps: List[dict] = []
    confidence: Optional[float] = None
    model_used: Optional[str] = None


class CoachingResponse(BaseModel):
    meeting_id: int
    title: str
    assessment: str
    user_say: str
    reasoning: str
    talk_improvements: List[str] = []
    model_used: Optional[str] = None
