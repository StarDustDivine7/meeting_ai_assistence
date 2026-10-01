import asyncio
from typing import Optional
from sqlalchemy.orm import Session
from db.database import SessionLocal
from db.models import Meeting, TranscriptSegment, MeetingStatus
from services.transcription import transcription_service
from services.chunking import chunking_service
from services.embeddings import embedding_service
from vector_store.faiss_store import FAISSStore
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MeetingProcessor:
    def __init__(self):
        self.transcription_service = transcription_service
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
    
    async def process_meeting(self, meeting_id: int) -> bool:
        """
        Process a meeting: transcribe audio, chunk, embed, and store in vector DB.
        
        Args:
            meeting_id: Meeting ID to process
            
        Returns:
            True if successful, False otherwise
        """
        db = SessionLocal()
        try:
            # Get meeting
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            if not meeting:
                logger.error(f"Meeting {meeting_id} not found")
                return False
            
            # Update status to processing
            meeting.status = MeetingStatus.PROCESSING
            db.commit()
            
            logger.info(f"Processing meeting {meeting_id}: {meeting.title}")
            
            # Step 1: Transcribe audio
            logger.info(f"Transcribing audio for meeting {meeting_id}")
            try:
                transcription = self.transcription_service.transcribe_audio_with_metadata(
                    meeting.audio_file_path
                )
                segments = transcription["segments"]
                meeting.duration = transcription["duration"]
                
                # Save transcript segments to database
                for seg in segments:
                    db_segment = TranscriptSegment(
                        meeting_id=meeting_id,
                        text=seg["text"],
                        start_time=seg["start_time"],
                        end_time=seg["end_time"]
                    )
                    db.add(db_segment)
                
                # Build full transcript
                full_transcript = " ".join([seg["text"] for seg in segments])
                meeting.transcript = full_transcript
                
                db.commit()
                logger.info(f"Transcription complete: {len(segments)} segments")
                
            except Exception as e:
                logger.error(f"Transcription failed: {str(e)}")
                meeting.status = MeetingStatus.FAILED
                meeting.error_message = f"Transcription failed: {str(e)}"
                db.commit()
                return False
            
            # Step 2: Chunk transcript
            logger.info(f"Chunking transcript for meeting {meeting_id}")
            try:
                chunks = self.chunking_service.chunk_transcript(segments)
                logger.info(f"Created {len(chunks)} chunks")
                
            except Exception as e:
                logger.error(f"Chunking failed: {str(e)}")
                meeting.status = MeetingStatus.FAILED
                meeting.error_message = f"Chunking failed: {str(e)}"
                db.commit()
                return False
            
            # Step 3: Generate embeddings
            logger.info(f"Generating embeddings for meeting {meeting_id}")
            try:
                chunk_texts = [chunk["text"] for chunk in chunks]
                embeddings = self.embedding_service.embed_batch(chunk_texts, batch_size=32)
                
                # Normalize embeddings
                embeddings = self.embedding_service.normalize_embeddings(embeddings)
                
            except Exception as e:
                logger.error(f"Embedding generation failed: {str(e)}")
                meeting.status = MeetingStatus.FAILED
                meeting.error_message = f"Embedding generation failed: {str(e)}"
                db.commit()
                return False
            
            # Step 4: Store in FAISS
            logger.info(f"Storing embeddings in FAISS for meeting {meeting_id}")
            try:
                store = FAISSStore(meeting_id)
                
                # Prepare metadata
                metadata = []
                for i, chunk in enumerate(chunks):
                    metadata.append({
                        "text": chunk["text"],
                        "start_time": chunk["start_time"],
                        "end_time": chunk["end_time"],
                        "chunk_index": chunk["chunk_index"]
                    })
                
                # Add embeddings to store
                store.add_embeddings(embeddings, metadata)
                logger.info(f"Stored {len(embeddings)} embeddings in FAISS")
                
            except Exception as e:
                logger.error(f"FAISS storage failed: {str(e)}")
                meeting.status = MeetingStatus.FAILED
                meeting.error_message = f"FAISS storage failed: {str(e)}"
                db.commit()
                return False
            
            # Update status to completed
            meeting.status = MeetingStatus.COMPLETED
            meeting.error_message = None
            db.commit()
            
            logger.info(f"Meeting {meeting_id} processing completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Unexpected error processing meeting {meeting_id}: {str(e)}")
            if meeting:
                meeting.status = MeetingStatus.FAILED
                meeting.error_message = f"Unexpected error: {str(e)}"
                db.commit()
            return False
        finally:
            db.close()
    
    async def process_meeting_sync(self, meeting_id: int) -> bool:
        """
        Synchronous wrapper for process_meeting.
        
        Args:
            meeting_id: Meeting ID to process
            
        Returns:
            True if successful, False otherwise
        """
        return await self.process_meeting(meeting_id)


# Singleton instance
meeting_processor = MeetingProcessor()


def process_meeting_task(meeting_id: int):
    """
    Synchronous task function for use with task queues like Celery.
    
    Args:
        meeting_id: Meeting ID to process
    """
    loop = asyncio.get_event_loop()
    loop.run_until_complete(meeting_processor.process_meeting(meeting_id))
