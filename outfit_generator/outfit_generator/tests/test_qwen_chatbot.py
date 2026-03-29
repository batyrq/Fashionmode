import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from models.qwen_chatbot import QwenStylistChatbot


CATALOG_PATH = Path(__file__).resolve().parents[1] / "catalog" / "sample_catalog.json"


class QwenStylistChatbotTests(unittest.TestCase):
    @patch("models.qwen_chatbot.AutoProcessor.from_pretrained", side_effect=RuntimeError("offline"))
    @patch("models.qwen_chatbot.AutoModelForVision2Seq.from_pretrained", side_effect=RuntimeError("offline"))
    def test_mock_mode_analyzes_query_and_sizes(self, *_):
        bot = QwenStylistChatbot(model_name="dummy", device="cpu")
        image = Image.new("RGB", (8, 8), color="white")

        result = bot.analyze_query(
            "Need an office outfit up to 5000 for size M",
            user_image=image,
            budget=None,
            sizes=["M"],
        )

        self.assertEqual(result["style"], "office")
        self.assertEqual(result["budget"], 5000)
        self.assertEqual(result["category"], "full_outfit")
        self.assertIn("M", result.get("sizes", []))

    def test_parse_json_response_handles_fenced_json(self):
        text = "Here is the result:\n```json\n{\"style\": \"casual\", \"budget\": 3000}\n```"
        parsed = QwenStylistChatbot._parse_json_response(text, dict)
        self.assertEqual(parsed, {"style": "casual", "budget": 3000})

    @patch("models.qwen_chatbot.AutoProcessor.from_pretrained", side_effect=RuntimeError("offline"))
    @patch("models.qwen_chatbot.AutoModelForVision2Seq.from_pretrained", side_effect=RuntimeError("offline"))
    def test_mock_mode_generates_complete_outfits(self, *_):
        bot = QwenStylistChatbot(model_name="dummy", device="cpu")
        with CATALOG_PATH.open("r", encoding="utf-8") as fh:
            catalog = json.load(fh)

        outfits = bot.generate_outfit_recommendations(
            {"style": "office", "budget": 70000, "colors": ["black"], "category": "full_outfit"},
            catalog,
        )

        self.assertGreaterEqual(len(outfits), 1)
        first_outfit = outfits[0]
        self.assertIn("items", first_outfit)
        self.assertTrue(all("url" in item for item in first_outfit["items"]))


if __name__ == "__main__":
    unittest.main()
