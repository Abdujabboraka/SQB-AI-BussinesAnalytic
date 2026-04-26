"""
OpenAI service wrapper for BiznesAI.
Handles all AI calls via OpenAI API (gpt-3.5-turbo / gpt-4) mimicking GeminiService.
"""
import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self, api_key=None):
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', '')
        self.model_name = "gpt-3.5-turbo"
        self.model = bool(self.api_key)  # Truthy if configured

    def _call(self, prompt: str, temperature: float = 0.3) -> dict:
        if not self.api_key:
            return {}
            
        url = "https://api.openai.com/v1/chat/completions"
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
            "temperature": temperature,
            "response_format": {"type": "json_object"}
        }
        
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if resp.status_code == 429:
                logger.error("OpenAI Rate Limit (429) or Quota Exceeded.")
                return {"is_mock": True, "_error": "quota_exceeded"}
                
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            result["provider"] = "openai"
            return result
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
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

    def analyze_demand(self, forecast_12: list, p10: int, p50: int, p90: int,
                       synthetic_demand_score: float, seasonality_weekly: list,
                       ramazon_boost_pct: float, navro_boost_pct: float,
                       request_obj=None) -> dict:
        context = self.build_context(request_obj)
        prompt = context + f"""
=== B BLOKI VAZIFASI: TALAB PROGNOZI ===
P50 (mediana): {p50}
Sintetik talab bali: {synthetic_demand_score}/100

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

    def evaluate_location(self, lat: float, lng: float, district: str,
                         competitors_300m: list, competitors_1km: list,
                         anchors: list, request_obj=None) -> dict:
        context = self.build_context(request_obj)
        prompt = context + f"""
=== C BLOKI VAZIFASI: JOYLASHUV TAHLILI ===
Joy: {district} | 300m raqobatchilar: {len(competitors_300m)}

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
Sarmoya: {kwargs.get('investment_uzs')} | ROI 12: {kwargs.get('roi_12mo')}

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

    def analyze_competition(self, competitors: list, business_type: str,
                            district: str, district_churn_rate: float,
                            request_obj=None) -> dict:
        context = self.build_context(request_obj)
        prompt = context + f"""
=== E BLOKI VAZIFASI: RAQOBAT VA RISKLAR ===
Biznes: {business_type} | Churn: {district_churn_rate}

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

    def final_decision(self, request_data, block_scores, composite_score) -> dict:
        prompt = f"""
=== YAKUNIY XULOSA (BANK EKSPERTI) ===
Kompozit ball: {composite_score}
Bloklar: {block_scores}

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
        logger.warning(f"OpenAI fallback used for block {block} (Quota Exceeded or Network Error)")
        return {
            "is_mock": True,
            "provider": "openai (fallback)",
            "commentary": "[OpenAI Quota Exceeded] - Limit tugaganligi sababli tizim avtomatik zaxira ma'lumotlarini taqdim etdi.",
            "gap_score": 50, "demand_score": 50, "location_score": 50, "market_risk_score": 50,
            "final_score": 50, "recommendation": "CAUTION"
        }
