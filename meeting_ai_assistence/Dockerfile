FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Pip settings
ENV PIP_DEFAULT_TIMEOUT=300
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# System dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel \
    && pip install \
    --no-cache-dir \
    --default-timeout=300 \
    --retries=10 \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

# Copy application
COPY . .

# Create required directories
RUN mkdir -p /app/uploads \
    /app/data \
    /app/vector_store

# Application port
EXPOSE 8000

# Start FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]