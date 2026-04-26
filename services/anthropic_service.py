"""
Anthropic service wrapper for BiznesAI.
Handles all AI calls via Anthropic API (Claude) mimicking GeminiService.
"""
import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

class AnthropicService:
    def __init__(self, api_key=None):
        self.api_key = api_key or getattr(settings, 'ANTHROPIC_API_KEY', '')
        self.model_name = "claude-3-haiku-20240307"
        self.model = bool(self.api_key)

    def _call(self, prompt: str, temperature: float = 0.3) -> dict:
        if not self.api_key:
            return {}
            
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": prompt + "\n\nFaqat JSON qaytar, hech qanday matn qo'shma."}
            ],
            "temperature": temperature
        }
        
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            content = data["content"][0]["text"]
            result = json.loads(content)
            result["provider"] = "anthropic"
            return result
        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            return {}

    def build_context(self, request_obj) -> str:
        if not request_obj: return ""
        return f"Biznes: {request_obj.business_type} | Tuman: {request_obj.district}"

    def analyze_market(self, **kwargs) -> dict:
        res = self._call("Market Analysis Task...")
        return res or self._mock_fallback("A")

    def analyze_demand(self, **kwargs) -> dict:
        res = self._call("Demand Analysis Task...")
        return res or self._mock_fallback("B")

    def evaluate_location(self, **kwargs) -> dict:
        res = self._call("Location Analysis Task...")
        return res or self._mock_fallback("C")

    def analyze_financial_viability(self, **kwargs) -> dict:
        res = self._call("Financial Analysis Task...")
        return res or self._mock_fallback("D")

    def analyze_competition(self, **kwargs) -> dict:
        res = self._call("Competition Analysis Task...")
        return res or self._mock_fallback("E")

    def final_decision(self, **kwargs) -> dict:
        res = self._call("Final Decision Task...")
        return res or self._mock_fallback("FINAL")

    def _mock_fallback(self, block: str):
        return {"is_mock": True, "commentary": "Anthropic fallback", "recommendation": "CAUTION"}
