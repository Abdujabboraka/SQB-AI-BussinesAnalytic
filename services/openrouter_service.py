"""
OpenRouter service — OpenAI-compatible proxy that routes to 100+ models.
Endpoint: https://openrouter.ai/api/v1/chat/completions
"""
import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Sen O'zbekiston bozorini tahlil qiluvchi, qattiqqo'l bank ekspertisan. "
    "Har doim to'g'ri JSON formatida javob qaytar. "
    "Hech qanday markdown (```json) ishlatma, faqat sof JSON matnini qaytar."
)


class OpenRouterService:
    def __init__(self, api_key=None):
        self.api_key   = api_key or getattr(settings, 'OPENROUTER_API_KEY', '')
        base           = getattr(settings, 'OPENROUTER_URL', 'https://openrouter.ai/api/v1').rstrip('/')
        self.api_url   = f"{base}/chat/completions"
        self.model_name = getattr(settings, 'OPENROUTER_MODEL', 'openai/gpt-4o-mini')
        self.model     = bool(self.api_key)

    def _call(self, prompt: str, temperature: float = 0.3) -> dict:
        if not self.api_key:
            return {}

        headers = {
            'Authorization':  f'Bearer {self.api_key}',
            'Content-Type':   'application/json',
            'HTTP-Referer':   'https://biznesai.sqb.uz',
            'X-Title':        'BiznesAI SQB',
        }
        payload = {
            'model':       self.model_name,
            'temperature': temperature,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user',   'content': prompt},
            ],
        }

        try:
            resp = requests.post(self.api_url, headers=headers, json=payload, timeout=25)
            if resp.status_code == 429:
                logger.error('OpenRouter rate-limit (429).')
                return {'is_mock': True, '_error': 'quota_exceeded'}
            if resp.status_code == 402:
                logger.error('OpenRouter insufficient credits (402).')
                return {'is_mock': True, '_error': 'no_credits'}
            resp.raise_for_status()
            content = resp.json()['choices'][0]['message']['content']
            result  = json.loads(content)
            result['provider'] = 'openrouter'
            return result
        except Exception as exc:
            logger.error(f'OpenRouter call failed: {exc}')
            return {}

    def build_context(self, request_obj) -> str:
        if not request_obj:
            return ''
        try:
            return (
                f"--- MIJOZ HAQIDA ---\n"
                f"Biznes: {request_obj.business_type} (Kategoriya: {request_obj.business_category_type})\n"
                f"Manzil: {request_obj.district}\n"
                f"Sarmoya: {request_obj.investment_amount} UZS\n"
                f"Kredit so'rovi: {request_obj.loan_amount} UZS\n"
            )
        except Exception:
            return ''

    # ── Block methods (same interface as all other services) ─────

    def analyze_market(self, business_type, mcc_code, district,
                       population=250000, competitor_count=12, request_obj=None) -> dict:
        prompt = self.build_context(request_obj) + f"""
=== A BLOKI: BOZOR TAHLILI ===
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
  "gap_analysis": "...",
  "commentary": "..."
}}
"""
        res = self._call(prompt)
        return res if res and not res.get('_error') else self._mock('A')

    def analyze_demand(self, forecast_12, p10, p50, p90,
                       synthetic_demand_score, seasonality_weekly,
                       ramazon_boost_pct, navro_boost_pct, request_obj=None) -> dict:
        prompt = self.build_context(request_obj) + f"""
=== B BLOKI: TALAB PROGNOZI ===
P50: {p50} | Sintetik ball: {synthetic_demand_score}/100

Faqat JSON qaytar:
{{
  "demand_score": 70,
  "realism_assessment": "...",
  "p50_validity": "...",
  "key_demand_drivers": ["..."],
  "demand_risks": ["..."],
  "seasonality_warnings": "...",
  "commentary": "..."
}}
"""
        res = self._call(prompt)
        return res if res and not res.get('_error') else self._mock('B')

    def evaluate_location(self, lat, lng, district,
                          competitors_300m, competitors_1km, anchors, request_obj=None) -> dict:
        prompt = self.build_context(request_obj) + f"""
=== C BLOKI: JOYLASHUV TAHLILI ===
Tuman: {district} | 300m raqobatchilar: {len(competitors_300m)}

Faqat JSON qaytar:
{{
  "location_score": 65,
  "anchor_effect_score": 40,
  "isochrone_demand_5min": 3500,
  "isochrone_demand_10min": 12000,
  "infrastructure_score": 60,
  "competitor_proximity_risk": "...",
  "commentary": "..."
}}
"""
        res = self._call(prompt)
        return res if res and not res.get('_error') else self._mock('C')

    def analyze_financial_viability(self, **kwargs) -> dict:
        prompt = self.build_context(kwargs.get('request_obj')) + f"""
=== D BLOKI: MOLIYAVIY TAHLIL ===
Sarmoya: {kwargs.get('investment_uzs')} | ROI 12oy: {kwargs.get('roi_12mo')}
BEP oylar: {kwargs.get('bep_months')} | MC ehtimol: {kwargs.get('mc_success_probability')}

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
        return res if res and not res.get('_error') else self._mock('D')

    def analyze_competition(self, competitors, business_type,
                            district, district_churn_rate, request_obj=None) -> dict:
        prompt = self.build_context(request_obj) + f"""
=== E BLOKI: RAQOBAT VA RISKLAR ===
Biznes: {business_type} | Churn: {district_churn_rate}%

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
        return res if res and not res.get('_error') else self._mock('E')

    def final_decision(self, request_data, block_scores, composite_score) -> dict:
        prompt = f"""
=== YAKUNIY XULOSA ===
Kompozit ball: {composite_score} | Bloklar: {block_scores}

Faqat JSON qaytar:
{{
  "recommendation": "CAUTION",
  "confidence": 0.65,
  "key_strengths": ["..."],
  "key_risks": ["..."],
  "commentary": "...",
  "credit_tier": "Moderate"
}}
"""
        res = self._call(prompt)
        return res if res and not res.get('_error') else self._mock('FINAL')

    def analyze_hotel(self, request_obj=None) -> dict:
        res = self._call(self.build_context(request_obj) + '=== HOTEL TAHLILI === Faqat JSON: {"location_score":60,"occupancy_forecast":[],"commentary":"..."}')
        return res if res and not res.get('_error') else self._mock('HOTEL')

    def analyze_construction(self, request_obj=None) -> dict:
        res = self._call(self.build_context(request_obj) + '=== QURILISH TAHLILI === Faqat JSON: {"cash_flow_timeline":[],"commentary":"..."}')
        return res if res and not res.get('_error') else self._mock('CONST')

    def analyze_textile(self, request_obj=None) -> dict:
        res = self._call(self.build_context(request_obj) + '=== TEKSTIL TAHLILI === Faqat JSON: {"export_readiness_score":50,"commentary":"..."}')
        return res if res and not res.get('_error') else self._mock('TEXT')

    def analyze_trade(self, request_obj=None) -> dict:
        res = self._call(self.build_context(request_obj) + '=== SAVDO TAHLILI === Faqat JSON: {"working_capital_needed":0,"commentary":"..."}')
        return res if res and not res.get('_error') else self._mock('TRADE')

    def _mock(self, block: str) -> dict:
        logger.warning(f'OpenRouter mock fallback for block {block}')
        return {
            'is_mock': True, 'provider': 'openrouter (fallback)',
            'commentary': '[OpenRouter xato] Zaxira ma\'lumot.',
            'gap_score': 50, 'demand_score': 50, 'location_score': 50,
            'market_risk_score': 50, 'viability_score': 50, 'recommendation': 'CAUTION',
        }
