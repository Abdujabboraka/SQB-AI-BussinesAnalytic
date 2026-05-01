"""
AICC service wrapper for BiznesAI.
Handles all AI calls via AICC API mimicking GeminiService.
"""
import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

class AICCService:
    def __init__(self, api_key=None, api_url=None):
        self.api_key = api_key or getattr(settings, 'AICC_API_KEY', '')
        base = api_url or getattr(settings, 'AICC_URL', 'https://api.ai.cc/v1')
        # Normalise: always point to the chat/completions endpoint
        base = base.rstrip('/')
        if base.endswith('/console'):
            base = base.replace('/console', '/v1')
        if not base.endswith('/chat/completions'):
            base = base.rstrip('/v1') if base.endswith('/v1') else base
            self.api_url = 'https://api.ai.cc/v1/chat/completions'
        else:
            self.api_url = base
        self.model_name = getattr(settings, 'AICC_MODEL', 'gpt-4o-mini')
        self.model = bool(self.api_key)

    def _call(self, prompt: str, temperature: float = 0.3) -> dict:
        if not self.api_key:
            return {}

        url = self.api_url

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "Sen O'zbekiston bozorini tahlil qiluvchi, qattiqqo'l bank ekspertisan. Har doim to'g'ri JSON formatida javob qaytar. Hech qanday markdown (```json) ishlatma, faqat sof JSON matnini qaytar."},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }
        
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=25)
            if resp.status_code != 200:
                logger.error(f"AICC Error {resp.status_code}: {resp.text}")
            
            if resp.status_code == 429:
                logger.error("AICC Rate Limit (429) or Quota Exceeded.")
                return {"is_mock": True, "_error": "quota_exceeded"}
                
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            result["provider"] = "aicc"
            return result
        except Exception as e:
            logger.error(f"AICC API call failed: {e}")
            return {}

    def build_context(self, request_obj) -> str:
        if not request_obj:
            return ""
        try:
            return (
                f"--- MIJOZ HAQIDA ---\n"
                f"Biznes: {request_obj.business_type} (Kategoriya: {request_obj.business_category_type})\n"
                f"Manzil: {request_obj.district}\n"
                f"Sarmoya: {request_obj.investment_amount} UZS\n"
                f"Kredit so'rovi: {request_obj.loan_amount} UZS\n"
            )
        except Exception:
            return ""

    def analyze_market(self, business_type: str, mcc_code: str, district: str,
                       population: int = 250000, competitor_count: int = 12,
                       request_obj=None) -> dict:
        context = self.build_context(request_obj)
        prompt = context + f"""
=== A BLOKI VAZIFASI: BOZOR TAHLILI ===
Biznes: {business_type} | Tuman: {district}
Aholi: {population} | Raqobatchilar: {competitor_count}

Faqat JSON qaytar:
{{
  "tam_uzs": 50000000000,
  "sam_uzs": 15000000000,
  "som_uzs": 3000000000,
  "saturation_index": 0.5,
  "gap_score": 60,
  "niche_opportunity_score": 55,
  "gap_analysis": "O'zbek tilida tahlil",
  "commentary": "O'zbek tilida tahlil"
}}
"""
        res = self._call(prompt)
        if res.get("_error"): return self._mock_fallback("A")
        return res or self._mock_fallback("A")

    def analyze_demand(self, **kwargs) -> dict:
        context = self.build_context(kwargs.get('request_obj'))
        prompt = context + f"""
=== B BLOKI VAZIFASI: TALAB PROGNOZI ===
Faqat JSON qaytar:
{{
  "demand_score": 70,
  "realism_assessment": "...",
  "p50_validity": "...",
  "key_demand_drivers": ["1", "2"],
  "demand_risks": ["1", "2"],
  "seasonality_warnings": "...",
  "commentary": "..."
}}
"""
        res = self._call(prompt)
        if res.get("_error"): return self._mock_fallback("B")
        return res or self._mock_fallback("B")

    def evaluate_location(self, **kwargs) -> dict:
        context = self.build_context(kwargs.get('request_obj'))
        prompt = context + f"""
=== C BLOKI VAZIFASI: JOYLASHUV TAHLILI ===
Faqat JSON qaytar:
{{
  "location_score": 65,
  "anchor_effect_score": 40,
  "infrastructure_score": 60,
  "traffic_assessment": "...",
  "parking_assessment": "...",
  "competitor_proximity_risk": "...",
  "commentary": "..."
}}
"""
        res = self._call(prompt)
        if res.get("_error"): return self._mock_fallback("C")
        return res or self._mock_fallback("C")

    def analyze_financial_viability(self, **kwargs) -> dict:
        context = self.build_context(kwargs.get('request_obj'))
        prompt = context + f"""
=== D BLOKI VAZIFASI: MOLIYAVIY TAHLIL ===
Faqat JSON qaytar:
{{
  "viability_score": 75,
  "bep_assessment": "...",
  "roi_assessment": "...",
  "cash_flow_assessment": "...",
  "ltv_cac_assessment": "...",
  "key_warnings": ["..."],
  "improvement_suggestions": ["..."],
  "sqb_compliance": "...",
  "commentary": "..."
}}
"""
        res = self._call(prompt)
        if res.get("_error"): return self._mock_fallback("D")
        return res or self._mock_fallback("D")

    def analyze_competition(self, **kwargs) -> dict:
        context = self.build_context(kwargs.get('request_obj'))
        prompt = context + f"""
=== E BLOKI VAZIFASI: RAQOBAT VA RISKLAR ===
Faqat JSON qaytar:
{{
  "market_risk_score": 50,
  "district_churn_rate": 15.0,
  "entry_barriers": ["..."],
  "risk_factors": ["..."],
  "recommendation_notes": "...",
  "commentary": "..."
}}
"""
        res = self._call(prompt)
        if res.get("_error"): return self._mock_fallback("E")
        return res or self._mock_fallback("E")

    def final_decision(self, **kwargs) -> dict:
        prompt = f"""
=== YAKUNIY XULOSA (BANK EKSPERTI) ===
Faqat JSON qaytar:
{{
  "recommendation": "CAUTION",
  "confidence": 0.65,
  "key_strengths": ["..."],
  "key_risks": ["..."],
  "commentary": "...",
  "credit_tier": "B - O'rtacha"
}}
"""
        res = self._call(prompt)
        if res.get("_error"): return self._mock_fallback("FINAL")
        return res or self._mock_fallback("FINAL")

    def _mock_fallback(self, block: str):
        logger.warning(f"AICC fallback used for block {block}")
        return {
            "is_mock": True,
            "provider": "aicc (fallback)",
            "commentary": "[AICC API Xatosi] - Limit tugaganligi yoki tarmoq xatosi sababli tizim avtomatik zaxira ma'lumotlarini taqdim etdi.",
            "gap_score": 50, "demand_score": 50, "location_score": 50, "market_risk_score": 50,
            "final_score": 50, "recommendation": "CAUTION"
        }
