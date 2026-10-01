from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from db.database import init_db
from api import auth, meetings, questions

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="AI-powered meeting transcription and Q&A system"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["auth"])
app.include_router(meetings.router, prefix=f"{settings.API_V1_PREFIX}/meetings", tags=["meetings"])
app.include_router(questions.router, prefix=f"{settings.API_V1_PREFIX}/meetings", tags=["questions"])


@app.on_event("startup")
def startup_event():
    """Initialize database on startup."""
    init_db()


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "Meeting AI Assistance API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
