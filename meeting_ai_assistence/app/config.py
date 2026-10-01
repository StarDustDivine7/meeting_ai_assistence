from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Meeting AI Assistance"
    
    # Database
    DATABASE_URL: str = "sqlite:///./meeting_ai.db"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # File Upload
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    # Browsers and operating systems report different MIME types for the same
    # audio container, so storage validation also checks the filename suffix.
    ALLOWED_AUDIO_TYPES: list = [
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/wave",
        "audio/mp4", "audio/m4a", "audio/aac", "audio/flac", "audio/x-flac",
        "audio/ogg", "audio/opus", "audio/webm", "application/octet-stream",
    ]
    ALLOWED_AUDIO_EXTENSIONS: list = [
        ".mp3", ".wav", ".m4a", ".mp4", ".aac", ".flac", ".ogg", ".opus", ".webm"
    ]
    
    # Transcription (Faster-Whisper)
    # `small` is a stronger multilingual model than `base` while remaining
    # practical on CPU. Override with WHISPER_MODEL_SIZE for larger machines.
    WHISPER_MODEL_SIZE: str = "small"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    
    # Embeddings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DEVICE: str = "cpu"
    
    # Vector Store
    VECTOR_STORE_DIR: str = "vector_store/data"
    FAISS_INDEX_TYPE: str = "IndexFlatIP"  # Inner product for cosine similarity
    
    # Chunking
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    
    # Background Worker
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
    # QA & RAG
    QA_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    TOP_K_RETRIEVAL: int = 5
    
    # Grok LLM / Groq / xAI Settings
    GROK_API_KEY: Optional[str] = None
    XAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    GROK_BASE_URL: str = "https://api.x.ai/v1"
    GROK_MODEL: str = "grok-2-latest"
    GROK_TEMPERATURE: float = 0.2
    GROK_MAX_TOKENS: int = 800
    GROK_TIMEOUT: float = 60.0
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.VECTOR_STORE_DIR, exist_ok=True)
