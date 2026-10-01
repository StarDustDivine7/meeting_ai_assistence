from typing import List, Dict
from app.config import settings


class ChunkingService:
    def __init__(self):
        self.chunk_size = settings.CHUNK_SIZE
        self.chunk_overlap = settings.CHUNK_OVERLAP
    
    def chunk_transcript(self, segments: List[Dict]) -> List[Dict]:
        """
        Chunk transcript segments into overlapping chunks.
        
        Args:
            segments: List of transcript segments with text, start_time, end_time
            
        Returns:
            List of chunks with text, start_time, end_time, chunk_index
        """
        chunks = []
        current_chunk = []
        current_text = ""
        chunk_start = None
        chunk_index = 0
        
        for segment in segments:
            segment_text = segment["text"]
            
            if chunk_start is None:
                chunk_start = segment["start_time"]
            
            # Add segment to current chunk
            current_chunk.append(segment)
            current_text += " " + segment_text
            current_text = current_text.strip()
            
            # Check if chunk size exceeded
            if len(current_text) >= self.chunk_size:
                chunks.append({
                    "text": current_text,
                    "start_time": chunk_start,
                    "end_time": segment["end_time"],
                    "chunk_index": chunk_index
                })
                chunk_index += 1
                
                # Start new chunk with overlap
                overlap_text = current_text[-self.chunk_overlap:] if len(current_text) > self.chunk_overlap else ""
                current_chunk = []
                current_text = overlap_text
                chunk_start = segment["start_time"] if overlap_text else None
        
        # Add remaining chunk
        if current_text:
            chunks.append({
                "text": current_text,
                "start_time": chunk_start if chunk_start else segments[0]["start_time"],
                "end_time": segments[-1]["end_time"],
                "chunk_index": chunk_index
            })
        
        return chunks
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Simple text chunking without timestamps.
        
        Args:
            text: Input text
            
        Returns:
            List of text chunks
        """
        chunks = []
        words = text.split()
        current_chunk = []
        current_length = 0
        
        for word in words:
            current_chunk.append(word)
            current_length += len(word) + 1  # +1 for space
            
            if current_length >= self.chunk_size:
                chunks.append(" ".join(current_chunk))
                # Keep overlap
                overlap_words = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else []
                current_chunk = overlap_words
                current_length = sum(len(w) + 1 for w in current_chunk)
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks


# Singleton instance
chunking_service = ChunkingService()
