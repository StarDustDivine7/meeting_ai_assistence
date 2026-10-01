from typing import List, Dict
from services.embeddings import embedding_service
from vector_store.faiss_store import FAISSStore


class RetrievalService:
    def __init__(self):
        self.embedding_service = embedding_service
    
    def retrieve_relevant_chunks(
        self,
        meeting_id: int,
        query: str,
        top_k: int = 5
    ) -> List[Dict]:
        """
        Retrieve relevant transcript chunks for a query.
        
        Args:
            meeting_id: Meeting ID
            query: User question
            top_k: Number of chunks to retrieve
            
        Returns:
            List of relevant chunks with metadata
        """
        # Load FAISS store for this meeting
        store = FAISSStore(meeting_id)
        
        if store.get_size() == 0:
            return []
        
        # Generate query embedding
        query_embedding = self.embedding_service.embed_text(query)
        
        # Search for similar chunks (get more to allow for deduplication)
        distances, indices, metadata = store.search(query_embedding, k=top_k * 2)
        
        # Add similarity scores to metadata and deduplicate by text
        seen_texts = set()
        results = []
        for i, meta in enumerate(metadata):
            text = meta.get("text", "")
            if text and text not in seen_texts:
                meta["similarity_score"] = float(distances[i])
                results.append(meta)
                seen_texts.add(text)
                if len(results) >= top_k:
                    break
        
        return results
    
    def retrieve_with_timestamps(
        self,
        meeting_id: int,
        query: str,
        top_k: int = 5
    ) -> List[Dict]:
        """
        Retrieve relevant chunks with timestamp information.
        
        Args:
            meeting_id: Meeting ID
            query: User question
            top_k: Number of chunks to retrieve
            
        Returns:
            List of chunks with timestamps
        """
        chunks = self.retrieve_relevant_chunks(meeting_id, query, top_k)
        
        # Ensure each chunk has timestamp info
        for chunk in chunks:
            if "start_time" not in chunk:
                chunk["start_time"] = 0.0
            if "end_time" not in chunk:
                chunk["end_time"] = 0.0
        
        return chunks


# Singleton instance
retrieval_service = RetrievalService()
