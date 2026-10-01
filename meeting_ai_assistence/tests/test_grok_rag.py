import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.grok_client import GrokClient
from services.qa import QAService
from schemas.question import QuestionWithAnswer, QuestionResponse


class TestGrokRAG(unittest.TestCase):
    def setUp(self):
        self.grok_client = GrokClient()
        self.qa_service = QAService()

    def test_grok_json_parsing_clean(self):
        sample_json = '''{
            "answer": "The team decided to launch the product in Q3.",
            "user_say": "Sarah mentioned: 'We are on track for September 15 launch.'",
            "reasoning": "Step 1: Analyzed statement at 12.5s where Sarah confirmed September launch. Step 2: Confirmed no objections.",
            "confidence": 0.95
        }'''
        parsed = self.grok_client._parse_grok_response(sample_json)
        self.assertEqual(parsed["answer"], "The team decided to launch the product in Q3.")
        self.assertIn("September 15", parsed["user_say"])
        self.assertIn("Analyzed statement", parsed["reasoning"])
        self.assertEqual(parsed["confidence"], 0.95)

    def test_grok_json_parsing_with_markdown_fences(self):
        sample_markdown = '''```json
        {
            "answer": "The store was acquired last year.",
            "user_say": "Speaker stated: 'We got a store. And we get a car.'",
            "reasoning": "Direct quote from 0.7s to 18.7s shows acquisition of assets.",
            "confidence": 0.9
        }
        ```'''
        parsed = self.grok_client._parse_grok_response(sample_markdown)
        self.assertEqual(parsed["answer"], "The store was acquired last year.")
        self.assertIn("We got a store", parsed["user_say"])

    def test_grok_fallback_when_no_api_key(self):
        chunks = [{
            "text": "When you look at this building, it actually begins only now when you're growing.",
            "start_time": 0.72,
            "end_time": 18.7,
            "similarity_score": 0.78
        }]
        res = self.grok_client.generate_rag_answer_sync(
            question="What is the building?",
            context="When you look at this building...",
            fallback_chunks=chunks
        )
        self.assertIn("answer", res)
        self.assertIn("user_say", res)
        self.assertIn("reasoning", res)
        self.assertGreaterEqual(res["confidence"], 0.0)

    def test_qa_service_formatting(self):
        rag_result = {
            "answer": "Test Answer",
            "user_say": "Test User Say",
            "reasoning": "Test Reasoning",
            "confidence": 0.88,
            "model_used": "grok-2-latest"
        }
        chunks = [{
            "text": "Sample chunk",
            "start_time": 1.0,
            "end_time": 5.0
        }]
        formatted = self.qa_service._format_response(rag_result, chunks)
        self.assertEqual(formatted["answer"], "Test Answer")
        self.assertEqual(formatted["answer_text"], "Test Answer")
        self.assertEqual(formatted["user_say"], "Test User Say")
        self.assertEqual(formatted["reasoning"], "Test Reasoning")
        self.assertEqual(formatted["model_used"], "grok-2-latest")
        self.assertEqual(len(formatted["timestamps"]), 1)

    def test_schemas(self):
        q = QuestionWithAnswer(
            question="What?",
            answer="Answer",
            answer_text="Answer",
            reasoning="Reasoning",
            user_say="User say",
            meeting_id=1,
            timestamps=[]
        )
        self.assertEqual(q.reasoning, "Reasoning")
        self.assertEqual(q.user_say, "User say")


if __name__ == "__main__":
    unittest.main()
