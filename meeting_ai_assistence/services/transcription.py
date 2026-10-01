from faster_whisper import WhisperModel
from typing import List, Dict
import os
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class TranscriptionService:
    def __init__(self):
        self.model = WhisperModel(
            settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE
        )
    
    def transcribe_audio(self, audio_path: str) -> List[Dict]:
        """Transcribe audio and return timestamped text segments."""
        result = self.transcribe_audio_with_metadata(audio_path)
        return result["segments"]

    def transcribe_audio_with_metadata(self, audio_path: str) -> Dict:
        """
        Transcribe audio using Whisper's automatic language detection.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Segments, detected language, and duration from the same inference pass.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        segments = []
        # Leave language unset so Whisper detects the spoken language. A larger
        # multilingual model improves recognition across languages and accents.
        segments_info, info = self.model.transcribe(
            audio_path,
            word_timestamps=True,
            beam_size=5,
            language=None,
            condition_on_previous_text=False,
            vad_filter=True,
            # Keep speech near pauses and quiet starts from being clipped.
            vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 500},
        )
        
        for segment in segments_info:
            if segment.text.strip():  # Only add non-empty segments
                segments.append({
                    "text": segment.text.strip(),
                    "start_time": segment.start,
                    "end_time": segment.end
                })
        
        if not segments:
            raise ValueError("No speech detected in audio file")

        language = getattr(info, "language", None)
        language_probability = getattr(info, "language_probability", None)
        logger.info(
            "Detected transcription language %s (confidence %s) for %s",
            language or "unknown",
            f"{language_probability:.2f}" if language_probability is not None else "unknown",
            os.path.basename(audio_path),
        )
        return {
            "segments": segments,
            "duration": getattr(info, "duration", 0.0) or 0.0,
            "language": language,
            "language_probability": language_probability,
        }
    
    def get_audio_duration(self, audio_path: str) -> float:
        """
        Get audio duration in seconds.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Duration in seconds
        """
        return self.transcribe_audio_with_metadata(audio_path)["duration"]


# Singleton instance
transcription_service = TranscriptionService()
