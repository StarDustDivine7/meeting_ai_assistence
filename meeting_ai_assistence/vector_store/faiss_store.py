import faiss
import numpy as np
import pickle
import os
from typing import List, Dict, Tuple
from app.config import settings


class FAISSStore:
    def __init__(self, meeting_id: int):
        self.meeting_id = meeting_id
        self.index_path = os.path.join(settings.VECTOR_STORE_DIR, f"meeting_{meeting_id}")
        self.metadata_path = os.path.join(settings.VECTOR_STORE_DIR, f"meeting_{meeting_id}_metadata.pkl")
        self.index = None
        self.metadata = []  # List of dicts with segment info
        
        self._load_or_create_index()
    
    def _load_or_create_index(self):
        """Load existing index or create new one."""
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            # Load existing index
            self.index = faiss.read_index(self.index_path)
            with open(self.metadata_path, 'rb') as f:
                self.metadata = pickle.load(f)
        else:
            # Create new index
            embedding_dim = 384  # Default for all-MiniLM-L6-v2
            if settings.FAISS_INDEX_TYPE == "IndexFlatIP":
                self.index = faiss.IndexFlatIP(embedding_dim)
            else:
                self.index = faiss.IndexFlatL2(embedding_dim)
    
    def add_embeddings(self, embeddings: np.ndarray, metadata: List[Dict]):
        """
        Add embeddings and metadata to the index.
        
        Args:
            embeddings: Numpy array of embeddings
            metadata: List of metadata dicts for each embedding
        """
        # Normalize embeddings for cosine similarity
        embeddings = embeddings.astype('float32')
        faiss.normalize_L2(embeddings)
        
        # Add to index
        self.index.add(embeddings)
        
        # Store metadata
        self.metadata.extend(metadata)
        
        # Save to disk
        self._save()
    
    def search(self, query_embedding: np.ndarray, k: int = 5) -> Tuple[np.ndarray, np.ndarray, List[Dict]]:
        """
        Search for similar embeddings.
        
        Args:
            query_embedding: Query embedding
            k: Number of results to return
            
        Returns:
            Tuple of (distances, indices, metadata)
        """
        if self.index.ntotal == 0:
            return np.array([]), np.array([]), []
        
        # Normalize query embedding
        query_embedding = query_embedding.astype('float32').reshape(1, -1)
        faiss.normalize_L2(query_embedding)
        
        # Search
        distances, indices = self.index.search(query_embedding, k)
        
        # Get metadata for results
        results_metadata = []
        for idx in indices[0]:
            if idx < len(self.metadata):
                results_metadata.append(self.metadata[idx])
        
        return distances[0], indices[0], results_metadata
    
    def _save(self):
        """Save index and metadata to disk."""
        faiss.write_index(self.index, self.index_path)
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.metadata, f)
    
    def delete(self):
        """Delete the index and metadata files."""
        self.delete_meeting_index(self.meeting_id)

    @staticmethod
    def delete_meeting_index(meeting_id: int):
        """Remove persisted vector data without loading or creating an index."""
        index_path = os.path.join(settings.VECTOR_STORE_DIR, f"meeting_{meeting_id}")
        metadata_path = os.path.join(settings.VECTOR_STORE_DIR, f"meeting_{meeting_id}_metadata.pkl")
        for path in (index_path, metadata_path):
            if os.path.exists(path):
                os.remove(path)
    
    def get_size(self) -> int:
        """Return the number of embeddings in the index."""
        return self.index.ntotal
