# Meeting AI Assistance

An AI-powered meeting transcription and Q&A system that transforms your audio meetings into searchable, interactive knowledge.

## 🌟 Features

- **Audio Transcription**: Upload meeting audio files (MP3, WAV, M4A, MP4, AAC, FLAC, OGG, OPUS, WEBM) for automatic transcription
- **AI-Powered Q&A**: Ask questions about your meetings and get intelligent answers with relevant timestamps
- **Talk Coaching**: Receive AI-powered feedback on communication style and presentation improvements
- **User Authentication**: Secure login and registration system
- **Meeting Management**: Create, view, update, and delete meetings
- **Real-time Processing**: Track transcription and processing status
- **Vector Search**: Fast semantic search across meeting transcripts using FAISS
- **Docker Support**: Easy deployment with Docker and Docker Compose

## 🏗️ Architecture

The project consists of two main components:

### Backend (`meeting_ai_assistence/`)
- **Framework**: FastAPI
- **Database**: PostgreSQL
- **ML/AI**:
  - Faster-Whisper for audio transcription
  - Sentence-Transformers for embeddings
  - FAISS-CPU for vector similarity search
  - Grok LLM for Q&A and coaching
- **Authentication**: JWT-based auth with passlib
- **API**: RESTful API with automatic OpenAPI documentation

### Frontend (`meeting_frontend/`)
- **Framework**: Streamlit
- **Features**:
  - User authentication (login/register)
  - Meeting upload interface
  - Meeting list with status tracking
  - AI chat interface for Q&A
  - Talk coaching reports
  - Transcript viewer
  - Meeting management (edit/delete)

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Docker & Docker Compose (for containerized deployment)

## 🚀 Installation

### Option 1: Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/StarDustDivine7/meeting_ai_assistence.git
   cd eden_home_project
   ```

2. **Configure environment variables**
   
   Create `.env` file in `meeting_ai_assistence/`:
   ```env
   DATABASE_URL=postgresql://postgres:postgres@postgres:5432/meeting_ai
   SECRET_KEY=your-secret-key-here
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   GROK_API_KEY=your-grok-api-key
   ```

3. **Build and start services**
   ```bash
   cd meeting_ai_assistence
   docker-compose up --build
   ```

4. **Access the application**
   - Frontend: http://localhost:8501
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - PostgreSQL: localhost:5432

### Option 2: Local Development

#### Backend Setup

1. **Navigate to backend directory**
   ```bash
   cd meeting_ai_assistence
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize database**
   ```bash
   # The database is automatically initialized on first run
   ```

6. **Start the backend**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

#### Frontend Setup

1. **Navigate to frontend directory**
   ```bash
   cd ../meeting_frontend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the frontend**
   ```bash
   streamlit run app.py --server.port 8501
   ```

## 📖 Usage

### 1. Register/Login
- Open the frontend at http://localhost:8501
- Click "Register" to create an account
- Login with your credentials

### 2. Upload a Meeting
- Click "Upload Meeting" from the sidebar
- Enter a title and optional description
- Select an audio file (MP3, WAV, M4A, etc.)
- Click "Upload" to start processing

### 3. View Meeting Status
- Go to "My Meetings" to see all your meetings
- Status indicators: COMPLETED, PROCESSING, FAILED
- Processing typically takes a few minutes depending on audio length

### 4. Ask Questions
- Click "View" on a completed meeting
- In the "AI Chat & Q&A" tab, type your question
- Click "Send" to get an AI-powered answer with:
  - Direct answer
  - Relevant transcript excerpts
  - Timestamps
  - AI reasoning trace

### 5. Get Talk Coaching
- In the "Talk Coaching" tab, click to generate coaching report
- Receive feedback on:
  - Communication style
  - Presentation improvements
  - Areas for development

### 6. View Transcript
- In the "Transcript" tab, view the full transcription
- Segments are organized by timestamps
- Searchable text

## 🔧 Configuration

### Backend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `sqlite:///./meeting_ai.db` |
| `SECRET_KEY` | JWT secret key | - |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration time | `30` |
| `GROK_API_KEY` | Grok LLM API key | - |
| `UPLOAD_DIR` | Upload directory | `./uploads` |
| `VECTOR_STORE_DIR` | Vector store directory | `./vector_store` |
| `EMBEDDING_MODEL` | Sentence transformer model | `all-MiniLM-L6-v2` |

### Frontend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_BASE_URL` | Backend API URL | `http://localhost:8000/api/v1` |

## 🔌 API Documentation

Once the backend is running, visit http://localhost:8000/docs for interactive API documentation.

### Main Endpoints

- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login user
- `GET /api/v1/meetings/` - List all meetings
- `POST /api/v1/meetings/` - Upload new meeting
- `GET /api/v1/meetings/{id}` - Get meeting details
- `PATCH /api/v1/meetings/{id}` - Update meeting
- `DELETE /api/v1/meetings/{id}` - Delete meeting
- `POST /api/v1/meetings/{id}/questions` - Ask a question
- `GET /api/v1/meetings/{id}/questions` - Get all questions
- `POST /api/v1/meetings/{id}/coaching` - Get coaching report

## 🐳 Docker Services

The `docker-compose.yml` defines three services:

### Backend
- Port: 8000
- Depends on: PostgreSQL
- Volumes: uploads, data, vector_store

### Frontend
- Port: 8501
- Depends on: Backend
- Environment: API_BASE_URL

### PostgreSQL
- Port: 5432
- Database: meeting_ai
- User: postgres
- Password: postgres
- Volume: postgres_data

## 🛠️ Troubleshooting

### Build Fails with CUDA Errors
**Issue**: Docker build fails trying to download CUDA packages on Apple Silicon.

**Solution**: The Dockerfile is configured to use CPU-only PyTorch. If you still encounter issues, ensure you have the latest Dockerfile with `--extra-index-url https://download.pytorch.org/whl/cpu`.

### Frontend Cannot Connect to Backend
**Issue**: "This site can't be reached" or connection refused.

**Solution**: 
- Ensure both services are running: `docker-compose ps`
- Check backend logs: `docker-compose logs backend`
- Verify API_BASE_URL is set correctly in docker-compose.yml

### Database Connection Errors
**Issue**: Cannot connect to PostgreSQL.

**Solution**:
- Check PostgreSQL is healthy: `docker-compose ps postgres`
- Verify DATABASE_URL in .env matches docker-compose configuration
- Restart services: `docker-compose restart`

### Processing Stuck at "Processing"
**Issue**: Meeting status remains "processing" indefinitely.

**Solution**:
- Check backend logs for errors: `docker-compose logs backend`
- Verify Grok API key is set correctly
- Ensure sufficient disk space for audio processing

### Large File Uploads Fail
**Issue**: Upload fails for large audio files.

**Solution**:
- Check file size limits in FastAPI configuration
- Increase timeout in docker-compose if needed
- Verify sufficient memory in Docker Desktop settings

## 📁 Project Structure

```
eden_home_project/
├── meeting_ai_assistence/          # Backend
│   ├── app/
│   │   ├── main.py                 # FastAPI app entry point
│   │   ├── config.py               # Configuration settings
│   │   └── models.py               # Database models
│   ├── api/
│   │   ├── auth.py                 # Authentication endpoints
│   │   ├── meetings.py             # Meeting CRUD endpoints
│   │   └── questions.py            # Q&A endpoints
│   ├── services/
│   │   ├── transcription.py        # Audio transcription
│   │   ├── embedding.py            # Text embeddings
│   │   └── qa.py                   # Q&A logic
│   ├── db/
│   │   └── database.py             # Database connection
│   ├── uploads/                    # Uploaded audio files
│   ├── data/                       # Processed data
│   ├── vector_store/               # FAISS index
│   ├── Dockerfile                  # Backend Docker image
│   ├── requirements.txt           # Python dependencies
│   ├── docker-compose.yml          # Docker orchestration
│   └── .env                        # Environment variables
│
├── meeting_frontend/               # Frontend
│   ├── app.py                      # Streamlit application
│   ├── Dockerfile                  # Frontend Docker image
│   └── requirements.txt           # Python dependencies
│
└── README.md                       # This file
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- Faster-Whisper for fast audio transcription
- Sentence-Transformers for semantic embeddings
- FAISS for efficient similarity search
- Streamlit for the beautiful UI
- FastAPI for the robust backend API
