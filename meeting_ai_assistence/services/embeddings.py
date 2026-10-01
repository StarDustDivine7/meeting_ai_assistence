from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Union
from app.config import settings


class EmbeddingService:
    def __init__(self):
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self.device = settings.EMBEDDING_DEVICE
    
    def embed_text(self, text: Union[str, List[str]]) -> np.ndarray:
        """
        Generate embeddings for text or list of texts.
        
        Args:
            text: Single text string or list of texts
            
        Returns:
            Numpy array of embeddings
        """
        embeddings = self.model.encode(
            text,
            convert_to_numpy=True,
            show_progress_bar=False,
            device=self.device
        )
        return embeddings
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Generate embeddings for a batch of texts.
        
        Args:
            texts: List of texts
            batch_size: Batch size for processing
            
        Returns:
            Numpy array of embeddings
        """
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=True,
            device=self.device
        )
        return embeddings
    
    def normalize_embeddings(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Normalize embeddings for cosine similarity.
        
        Args:
            embeddings: Numpy array of embeddings
            
        Returns:
            Normalized embeddings
        """
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings / norms


# Singleton instance
embedding_service = EmbeddingService()
