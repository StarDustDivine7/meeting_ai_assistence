import os
import uuid
from typing import Optional
from fastapi import UploadFile, HTTPException
from app.config import settings


class StorageService:
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
    
    async def save_audio_file(self, file: UploadFile) -> str:
        """
        Save uploaded audio file to disk.
        
        Args:
            file: UploadFile object
            
        Returns:
            Path to saved file
        """
        # MIME types vary across browsers; validate both the declared type and
        # filename extension so valid MP3/M4A uploads are not rejected.
        original_filename = file.filename or "audio"
        file_extension = os.path.splitext(original_filename)[1].lower()
        content_type = (file.content_type or "").lower().split(";", 1)[0]
        if (
            file_extension not in settings.ALLOWED_AUDIO_EXTENSIONS
            and content_type not in settings.ALLOWED_AUDIO_TYPES
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unsupported audio format. Upload MP3, WAV, M4A, MP4, AAC, "
                    "FLAC, OGG, OPUS, or WEBM audio."
                ),
            )

        # Generate unique filename
        if not file_extension:
            file_extension = ".mp3" if content_type in {"audio/mpeg", "audio/mp3"} else ".wav"
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(self.upload_dir, unique_filename)
        
        # Save file
        try:
            with open(file_path, "wb") as buffer:
                content = await file.read()
                if len(content) > settings.MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE} bytes"
                    )
                buffer.write(content)
        except HTTPException:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")
        
        return file_path
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from disk.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception:
            return False
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if file exists.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if exists, False otherwise
        """
        return os.path.exists(file_path)


# Singleton instance
storage_service = StorageService()
