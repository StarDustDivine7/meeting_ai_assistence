import os
import json
import re
import logging
import asyncio
import time
from typing import Dict, List, Optional, Any
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class GrokClient:
    """
    Client for interacting with LLM models (xAI Grok or Groq).
    Auto-detects provider based on API key prefix:
      - 'gsk_...': Groq API (https://api.groq.com/openai/v1) with openai/gpt-oss-120b / qwen3.8-27b
      - 'xai-...': xAI Grok API (https://api.x.ai/v1) with grok-2-latest / grok-beta
    Supports multi-turn chat, structured RAG answers, speaker attribution ('user say'),
    step-by-step reasoning, and actionable coaching ideas ('talk improvements').
    """

    def __init__(self):
        self.temperature = settings.GROK_TEMPERATURE
        self.max_tokens = settings.GROK_MAX_TOKENS
        self.timeout = settings.GROK_TIMEOUT

    def _get_api_key(self) -> str:
        return (
            settings.GROK_API_KEY
            or settings.XAI_API_KEY
            or settings.GROQ_API_KEY
            or os.getenv("GROK_API_KEY")
            or os.getenv("XAI_API_KEY")
            or os.getenv("GROQ_API_KEY")
            or ""
        ).strip()

    def is_configured(self) -> bool:
        """Check if an API key is configured."""
        key = self._get_api_key()
        return bool(key and not key.startswith("your_"))

    def _resolve_provider(self, api_key: str):
        """
        Auto-detect provider (Groq vs xAI) based on key prefix or user settings.
        Groq keys start with 'gsk_', xAI keys start with 'xai-'.
        """
        if api_key.startswith("gsk_") or "groq" in settings.GROK_BASE_URL.lower():
            base_url = "https://api.groq.com/openai/v1"
            # If user left default model as grok-2-latest, use Groq's top chat model
            model = settings.GROK_MODEL
            if not model or "grok" in model.lower():
                model = "openai/gpt-oss-120b"
            return base_url, model, "groq"
        else:
            base_url = settings.GROK_BASE_URL.rstrip("/")
            model = settings.GROK_MODEL or "grok-2-latest"
            return base_url, model, "xai"

    def build_system_prompt(self) -> str:
        return (
            "You are an expert Meeting AI Intelligence & Conversation Coach powered by Grok/Groq.\n"
            "Your task is to analyze meeting context and transcript excerpts to provide a clear, "
            "deeply reasoned answer to the user's inquiry, detail what participants said, "
            "explain your reasoning, and suggest actionable ideas on what should be changed or improved in the talk.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Base your answers strictly on the provided transcript and meeting context.\n"
            "2. MULTILINGUAL & TRANSLATION REQUIREMENT:\n"
            "   - When the user asks in English (or asks 'tell me in english' / 'what did participants say'), ALWAYS provide the 'answer', 'user_say', 'reasoning', and 'talk_improvements' entirely in clear, natural English.\n"
            "   - If the transcript contains Hindi, Urdu, or another non-English language, TRANSLATE what was said into English in both 'answer' and 'user_say'. Explain what the participants discussed and meant. Do NOT output raw untranslated foreign-language quotes as your primary answer.\n"
            "3. 'user_say': Summarize and translate what participants said in the meeting relevant to the topic. Cite timestamps where available.\n"
            "4. 'reasoning': Provide clear step-by-step reasoning explaining which excerpts were examined and how the conclusion was reached.\n"
            "5. 'talk_improvements': Provide 2 to 3 concise, actionable recommendations on what could be changed or improved in the talk/conversation (e.g. clarity, defining next steps, confirming responsibilities).\n"
            "6. 'answer': Provide a direct, polished answer in English.\n"
            "7. 'confidence': A numeric score from 0.0 to 1.0.\n\n"
            "You MUST respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "answer": "Direct answer in clear English.",\n'
            '  "user_say": "Clear English summary and translation of what participants said with timestamps.",\n'
            '  "reasoning": "Step-by-step analytical reasoning explaining how the answer was deduced.",\n'
            '  "talk_improvements": [\n'
            '    "Actionable recommendation 1 on what to change in the talk",\n'
            '    "Actionable recommendation 2"\n'
            '  ],\n'
            '  "confidence": 0.95\n'
            "}"
        )

    def build_coaching_prompt(self, meeting_title: str, context: str) -> str:
        return (
            f"=== MEETING TITLE ===\n{meeting_title}\n\n"
            f"=== MEETING TRANSCRIPT ===\n{context}\n\n"
            "Please provide a comprehensive conversation coaching review of this meeting in English:\n"
            "Analyze the communication style, tone, clarity, speaker collaboration, and decision-making.\n"
            "If the transcript contains Hindi or another language, translate and analyze it in clear English.\n"
            "What should be changed in the talk according to this conversation?\n"
            "Return your analysis in valid JSON format with keys: 'answer', 'user_say', 'reasoning', 'talk_improvements', 'confidence'."
        )

    def _parse_grok_response(self, raw_text: str) -> Dict[str, Any]:
        """Safely parse the Grok/Groq LLM response into structured fields."""
        cleaned = raw_text.strip()

        # Strip markdown code blocks if present
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        # Try direct JSON parse
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "answer" in parsed:
                improvements = parsed.get("talk_improvements")
                if isinstance(improvements, str):
                    improvements = [improvements]
                elif not isinstance(improvements, list):
                    improvements = []
                return {
                    "answer": str(parsed.get("answer", "")).strip(),
                    "user_say": str(parsed.get("user_say", "")).strip(),
                    "reasoning": str(parsed.get("reasoning", "")).strip(),
                    "talk_improvements": [str(x).strip() for x in improvements if x],
                    "confidence": float(parsed.get("confidence", 0.9)),
                }
        except Exception:
            pass

        # Try to find JSON within the text
        json_match = re.search(r"(\{[\s\S]*\})", cleaned)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                if isinstance(parsed, dict) and "answer" in parsed:
                    improvements = parsed.get("talk_improvements")
                    if isinstance(improvements, str):
                        improvements = [improvements]
                    elif not isinstance(improvements, list):
                        improvements = []
                    return {
                        "answer": str(parsed.get("answer", "")).strip(),
                        "user_say": str(parsed.get("user_say", "")).strip(),
                        "reasoning": str(parsed.get("reasoning", "")).strip(),
                        "talk_improvements": [str(x).strip() for x in improvements if x],
                        "confidence": float(parsed.get("confidence", 0.9)),
                    }
            except Exception:
                pass

        # Try to auto-close unclosed JSON or extract fields with regex
        ans_m = re.search(r'"answer"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)', cleaned)
        user_m = re.search(r'"user_say"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)', cleaned)
        reason_m = re.search(r'"reasoning"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)', cleaned)
        if ans_m:
            answer_text = ans_m.group(1).replace(r'\"', '"').replace(r'\n', '\n').strip()
            user_say_text = user_m.group(1).replace(r'\"', '"').replace(r'\n', '\n').strip() if user_m else "Summarized from meeting transcript."
            reason_text = reason_m.group(1).replace(r'\"', '"').replace(r'\n', '\n').strip() if reason_m else "Deduced through contextual transcript analysis."
            return {
                "answer": answer_text,
                "user_say": user_say_text,
                "reasoning": reason_text,
                "talk_improvements": [
                    "Ensure key decisions and action items are confirmed before ending the topic.",
                    "Encourage clear documentation of requirements and responsibilities."
                ],
                "confidence": 0.88,
            }

        # Fallback heuristic parsing if answered in plain text
        return {
            "answer": cleaned,
            "user_say": "Direct statements from the meeting transcript.",
            "reasoning": "Derived through contextual meeting analysis.",
            "talk_improvements": [
                "Ensure key decisions and action items are confirmed before ending the topic.",
                "Encourage open clarification if statements appear ambiguous or incomplete."
            ],
            "confidence": 0.85,
        }

    async def generate_rag_answer_async(
        self,
        question: str,
        context: str,
        meeting_title: Optional[str] = None,
        meeting_description: Optional[str] = None,
        duration: Optional[float] = None,
        history: Optional[List[Dict[str, str]]] = None,
        fallback_chunks: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Generate answer, user statements analysis, reasoning, and talk improvement ideas
        using Grok/Groq LLM asynchronously.
        """
        api_key = self._get_api_key()

        if not api_key or api_key.startswith("your_"):
            return self._generate_fallback(question, context, fallback_chunks or [])

        base_url, model, provider = self._resolve_provider(api_key)
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        system_prompt = self.build_system_prompt()
        
        # Build prompt with metadata
        meta = []
        if meeting_title:
            meta.append(f"Meeting Title: {meeting_title}")
        if meeting_description:
            meta.append(f"Meeting Description: {meeting_description}")
        if duration:
            meta.append(f"Meeting Duration: {duration:.1f}s")
        meta_str = " | ".join(meta) if meta else "Meeting Session"

        messages = [{"role": "system", "content": system_prompt}]

        # Append previous conversation history if provided
        if history:
            for turn in history[-3:]:  # Keep recent 3 turns to minimize token consumption
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content[:300]})

        user_content = (
            f"=== MEETING CONTEXT ({meta_str}) ===\n"
            f"{context}\n"
            f"====================================\n\n"
            f"USER INQUIRY: {question}\n\n"
            "REQUIREMENT: Provide a structured JSON response in clear English. If the meeting transcript contains Hindi or another language, translate the statements and summarize them in English. Detail what participants said ('user_say'), explain your step-by-step reasoning ('reasoning'), and provide actionable talk improvements ('talk_improvements')."
        )
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": min(self.max_tokens, 800),
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

                # If rate limited (429), wait 1.5s and retry once
                if response.status_code == 429:
                    logger.warning("Rate limited (429). Pausing 1.5s to retry once...")
                    await asyncio.sleep(1.5)
                    response = await client.post(url, headers=headers, json=payload)

                if response.status_code != 200:
                    logger.error(f"LLM API error ({provider}) HTTP {response.status_code}: {response.text}")
                    fallback = self._generate_fallback(question, context, fallback_chunks or [])
                    fallback["reasoning"] += f"\n\n[Note: LLM provider returned HTTP {response.status_code}]"
                    return fallback

                data = response.json()
                raw_content = (
                    data.get("choices", [{}])[0].get("message", {}).get("content", "")
                )
                parsed = self._parse_grok_response(raw_content)
                parsed["model_used"] = f"{provider}:{model}"
                return parsed

        except Exception as e:
            logger.error(f"Failed to query LLM ({provider}): {str(e)}", exc_info=True)
            fallback = self._generate_fallback(question, context, fallback_chunks or [])
            fallback["reasoning"] += f"\n\n[Note: LLM call error: {str(e)}]"
            return fallback

    def generate_rag_answer_sync(
        self,
        question: str,
        context: str,
        meeting_title: Optional[str] = None,
        meeting_description: Optional[str] = None,
        duration: Optional[float] = None,
        history: Optional[List[Dict[str, str]]] = None,
        fallback_chunks: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for generating RAG answer with Grok/Groq LLM."""
        api_key = self._get_api_key()

        if not api_key or api_key.startswith("your_"):
            return self._generate_fallback(question, context, fallback_chunks or [])

        base_url, model, provider = self._resolve_provider(api_key)
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        system_prompt = self.build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]

        if history:
            for turn in history[-3:]:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content[:300]})

        meta = f"{meeting_title or 'Meeting'}"
        user_content = (
            f"=== MEETING CONTEXT ({meta}) ===\n"
            f"{context}\n"
            f"================================\n\n"
            f"USER INQUIRY: {question}\n\n"
            "REQUIREMENT: Provide a structured JSON response in clear English. If the meeting transcript contains Hindi or another language, translate the statements and summarize them in English. Detail what participants said ('user_say'), explain your step-by-step reasoning ('reasoning'), and provide actionable talk improvements ('talk_improvements')."
        )
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": min(self.max_tokens, 800),
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code == 429:
                    logger.warning("Rate limited (429). Pausing 1.5s to retry once...")
                    time.sleep(1.5)
                    response = client.post(url, headers=headers, json=payload)

                if response.status_code != 200:
                    logger.error(f"LLM API error ({provider}) HTTP {response.status_code}: {response.text}")
                    fallback = self._generate_fallback(question, context, fallback_chunks or [])
                    fallback["reasoning"] += f"\n\n[Note: LLM API returned HTTP {response.status_code}]"
                    return fallback

                data = response.json()
                raw_content = (
                    data.get("choices", [{}])[0].get("message", {}).get("content", "")
                )
                parsed = self._parse_grok_response(raw_content)
                parsed["model_used"] = f"{provider}:{model}"
                return parsed
        except Exception as e:
            logger.error(f"Failed to query LLM ({provider}): {str(e)}", exc_info=True)
            fallback = self._generate_fallback(question, context, fallback_chunks or [])
            fallback["reasoning"] += f"\n\n[Note: LLM call failed: {str(e)}]"
            return fallback

    async def generate_coaching_review_async(
        self,
        meeting_title: str,
        full_transcript: str,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive conversation coaching analysis for the meeting:
        What should be changed in the talk according to the conversation dynamics.
        """
        api_key = self._get_api_key()
        if not api_key or api_key.startswith("your_"):
            return {
                "answer": "Conversation Coaching Review: The meeting dialogue presents ideas and discussion points.",
                "user_say": full_transcript[:300] if full_transcript else "No transcript available.",
                "reasoning": "Analyzed available speech segments to identify meeting conversation patterns.",
                "talk_improvements": [
                    "Clarify commitments and next steps explicitly before closing topics.",
                    "Ensure equal airtime and invite quieter participants to contribute.",
                    "Summarize agreed outcomes to prevent misunderstandings."
                ],
                "confidence": 0.8,
                "model_used": "heuristic-coach",
            }

        base_url, model, provider = self._resolve_provider(api_key)
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        system_prompt = (
            "You are an executive Communication Coach and Meeting Analyst.\n"
            "Analyze the meeting transcript thoroughly and produce a structured coaching assessment.\n"
            "Evaluate:\n"
            "1. Conversation clarity, tone, and balance.\n"
            "2. What participants did well.\n"
            "3. What should be changed or improved in the talk (specific phrasing, structure, action items).\n"
            "Return valid JSON only with keys: 'answer', 'user_say', 'reasoning', 'talk_improvements', 'confidence'."
        )

        user_prompt = (
            f"Meeting Title: {meeting_title}\n\n"
            f"Transcript:\n{full_transcript[:6000]}\n\n"
            "What should be changed in the talk according to this conversation? Provide constructive advice."
        )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.25,
            "max_tokens": self.max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    parsed = self._parse_grok_response(raw)
                    parsed["model_used"] = f"{provider}:{model}"
                    return parsed
        except Exception as e:
            logger.error(f"Failed to generate coaching review: {e}")

        return {
            "answer": "Coaching feedback: Structure conversation points clearly with defined goals.",
            "user_say": full_transcript[:300] if full_transcript else "",
            "reasoning": "Transcript review shows opportunities for improved alignment.",
            "talk_improvements": [
                "Establish clear meeting objectives at the start.",
                "Confirm consensus and designate specific owners for next steps."
            ],
            "confidence": 0.8,
            "model_used": "fallback-coach",
        }

    def _generate_fallback(
        self,
        question: str,
        context: str,
        chunks: List[Dict],
    ) -> Dict[str, Any]:
        """High-quality heuristic fallback when API key is not configured."""
        if not chunks and not context:
            return {
                "answer": "No relevant statements or transcript segments were found in this meeting for your question.",
                "user_say": "No participant statements matched the query.",
                "reasoning": "The semantic vector store returned zero matching segments for the inquiry.",
                "talk_improvements": [
                    "Clarify discussion topics and ensure key subjects are spoken to directly in the meeting."
                ],
                "confidence": 0.0,
                "model_used": "rag-vector-retrieval",
            }

        top_chunk = chunks[0] if chunks else {"text": context[:300], "start_time": 0.0, "end_time": 0.0}
        top_text = top_chunk.get("text", "").strip()
        start = top_chunk.get("start_time", 0.0)
        end = top_chunk.get("end_time", 0.0)

        user_statements = []
        for c in chunks[:3]:
            s_time = c.get("start_time", 0.0)
            e_time = c.get("end_time", 0.0)
            txt = c.get("text", "").strip()
            user_statements.append(f"• [{s_time:.1f}s - {e_time:.1f}s]: \"{txt}\"")
        user_say_text = "\n".join(user_statements) if user_statements else f'"{top_text}"'

        answer = f"According to the meeting transcript, the discussion noted: \"{top_text}\""

        reasoning = (
            f"1. Context Retrieval: Evaluated the meeting transcript using sentence-transformer semantic embeddings against query: '{question}'.\n"
            f"2. Speaker Statement Analysis: Identified primary relevant segment at [{start:.1f}s - {end:.1f}s].\n"
            f"3. Deduction: The participants explicitly stated: \"{top_text[:180]}...\"."
        )

        talk_improvements = [
            "Conclude key statements with explicit agreements rather than open-ended remarks.",
            "Define concrete deliverables and assign responsible individuals.",
            "Ask clarifying questions when complex ideas are introduced to ensure mutual understanding."
        ]

        score = top_chunk.get("similarity_score", 0.75)
        confidence = min(max(float(score), 0.0), 1.0) if score else 0.75

        return {
            "answer": answer,
            "user_say": user_say_text,
            "reasoning": reasoning,
            "talk_improvements": talk_improvements,
            "confidence": confidence,
            "model_used": "rag-fallback-retrieval",
        }


# Singleton instance
grok_client = GrokClient()
