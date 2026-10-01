from typing import List, Dict, Optional, Any
from services.retrieval import retrieval_service
from services.embeddings import embedding_service
from services.grok_client import grok_client
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class QAService:
    """
    RAG (Retrieval-Augmented Generation) Q&A service.
    Combines semantic FAISS retrieval over meeting transcript segments
    with Grok/Groq LLM reasoning to explain what speakers/users said,
    answer questions, explain reasoning, and suggest conversation improvements.
    """

    def __init__(self):
        self.retrieval_service = retrieval_service
        self.embedding_service = embedding_service
        self.grok_client = grok_client
        self.top_k = 3  # Keep compact to strictly limit LLM tokens per minute
        self._coaching_cache: Dict[int, Dict[str, Any]] = {}

    async def answer_question_async(
        self,
        meeting_id: int,
        question: str,
        meeting_title: Optional[str] = None,
        meeting_description: Optional[str] = None,
        duration: Optional[float] = None,
        full_transcript: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Answer a question about a meeting using FAISS retrieval + LLM reasoning & coaching (async).
        """
        # Retrieve relevant chunks with timestamps
        chunks = self.retrieval_service.retrieve_with_timestamps(
            meeting_id,
            question,
            top_k=self.top_k
        )

        # Build context from retrieved chunks
        context = self._build_context(chunks, full_transcript)

        # Generate answer with Grok/Groq LLM
        rag_result = await self.grok_client.generate_rag_answer_async(
            question=question,
            context=context,
            meeting_title=meeting_title,
            meeting_description=meeting_description,
            duration=duration,
            history=history,
            fallback_chunks=chunks,
        )

        return self._format_response(rag_result, chunks)

    def answer_question(
        self,
        meeting_id: int,
        question: str,
        meeting_title: Optional[str] = None,
        meeting_description: Optional[str] = None,
        duration: Optional[float] = None,
        full_transcript: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Answer a question about a meeting using FAISS retrieval + LLM reasoning & coaching (sync).
        """
        chunks = self.retrieval_service.retrieve_with_timestamps(
            meeting_id,
            question,
            top_k=self.top_k
        )

        context = self._build_context(chunks, full_transcript)

        rag_result = self.grok_client.generate_rag_answer_sync(
            question=question,
            context=context,
            meeting_title=meeting_title,
            meeting_description=meeting_description,
            duration=duration,
            history=history,
            fallback_chunks=chunks,
        )

        return self._format_response(rag_result, chunks)

    async def get_conversation_coaching(
        self,
        meeting_id: int,
        meeting_title: str,
        full_transcript: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate in-depth conversation coaching on what should be changed or improved in the talk.
        Caches per meeting to strictly limit LLM API calls.
        """
        if not force_refresh and meeting_id in self._coaching_cache:
            return self._coaching_cache[meeting_id]

        context = full_transcript or ""
        if not context:
            # Fallback to chunks
            chunks = self.retrieval_service.retrieve_with_timestamps(meeting_id, "meeting summary overview", top_k=3)
            context = "\n".join([c.get("text", "") for c in chunks])

        # Limit context length to avoid rate limits
        if len(context) > 1500:
            context = context[:1500]

        result = await self.grok_client.generate_coaching_review_async(
            meeting_title=meeting_title or "Meeting Session",
            full_transcript=context,
        )
        self._coaching_cache[meeting_id] = result
        return result

    def _build_context(self, chunks: List[Dict], full_transcript: Optional[str] = None) -> str:
        """Format retrieved chunks compactly for LLM context to stay within rate limits."""
        context_parts = []
        for i, chunk in enumerate(chunks[:3]):
            start = chunk.get("start_time", 0.0)
            end = chunk.get("end_time", 0.0)
            text = chunk.get("text", "").strip()
            if len(text) > 350:
                text = text[:350] + "..."
            context_parts.append(f"[Excerpt {i+1} | {start:.1f}s - {end:.1f}s]:\n\"{text}\"")

        context = "\n\n".join(context_parts)

        # Include brief transcript excerpt ONLY if no chunks were found
        if not context and full_transcript:
            context = f"--- Meeting Transcript ---\n{full_transcript[:1200]}"

        return context or "No transcript segments found."

    def _format_response(self, rag_result: Dict[str, Any], chunks: List[Dict]) -> Dict[str, Any]:
        """Format the unified response dictionary."""
        timestamps = []
        for chunk in chunks:
            timestamps.append({
                "start_time": chunk.get("start_time", 0.0),
                "end_time": chunk.get("end_time", 0.0),
                "text": chunk.get("text", "")[:120] + "..." if len(chunk.get("text", "")) > 120 else chunk.get("text", "")
            })

        answer = rag_result.get("answer", "").strip()
        user_say = rag_result.get("user_say", "").strip()
        reasoning = rag_result.get("reasoning", "").strip()
        talk_improvements = rag_result.get("talk_improvements", [])
        confidence = rag_result.get("confidence", 0.8)
        model_used = rag_result.get("model_used", "grok-llm")

        return {
            "answer": answer,
            "answer_text": answer,
            "user_say": user_say,
            "reasoning": reasoning,
            "talk_improvements": talk_improvements,
            "relevant_segments": chunks,
            "timestamps": timestamps,
            "confidence": confidence,
            "model_used": model_used,
        }


# Singleton instance
qa_service = QAService()
