"""
HuggingFace Generation service wrapper for BiznesAI.
Used for text generation (Llama-3 etc) via HF Inference API.
"""
import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

class HuggingFaceGenService:
    def __init__(self, api_key=None):
        self.api_key = api_key or getattr(settings, 'HUGGINGFACE_API_TOKEN', '')
        self.model_name = "meta-llama/Meta-Llama-3-8B-Instruct"
        self.model = bool(self.api_key)

    def _call(self, prompt: str) -> dict:
        if not self.api_key: return {}
        url = f"https://api-inference.huggingface.co/models/{self.model_name}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"inputs": prompt, "parameters": {"max_new_tokens": 500}}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            resp.raise_for_status()
            # Simple parsing (HF returns list of dicts)
            res_text = resp.json()[0]['generated_text']
            # Try to find JSON in output
            if "{" in res_text:
                res_text = res_text[res_text.find("{"):res_text.rfind("}")+1]
                return json.loads(res_text)
            return {}
        except Exception as e:
            logger.error(f"HF Gen failed: {e}")
            return {}

    def analyze_market(self, **kwargs) -> dict: return self._mock_fallback("A")
    def analyze_demand(self, **kwargs) -> dict: return self._mock_fallback("B")
    def evaluate_location(self, **kwargs) -> dict: return self._mock_fallback("C")
    def analyze_financial_viability(self, **kwargs) -> dict: return self._mock_fallback("D")
    def analyze_competition(self, **kwargs) -> dict: return self._mock_fallback("E")
    def final_decision(self, **kwargs) -> dict: return self._mock_fallback("FINAL")

    def _mock_fallback(self, block: str):
        return {"is_mock": True, "commentary": "HuggingFace fallback", "recommendation": "CAUTION"}
