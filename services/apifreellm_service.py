"""
apifreellm service — free Llama-3 inference.
Non-standard API: POST {"message": "..."} → {"response": "...", "model": "llama-3"}
Used as last-resort free fallback before mock mode.
"""
import json
import logging
import re
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PREFIX = (
    "Sen O'zbekiston bozorini tahlil qiluvchi bank ekspertisan. "
    "Faqat JSON formatida javob qaytar. Markdown ishlatma.\n\n"
)


class ApiFreeLLMService:
    def __init__(self, api_key=None):
        self.api_key    = api_key or getattr(settings, 'APIFREELLM_API_KEY', '')
        self.api_url    = getattr(settings, 'APIFREELLM_URL', 'https://apifreellm.com/api/v1/chat')
        self.model_name = 'llama-3'
        self.model      = bool(self.api_key)

    def _call(self, prompt: str) -> dict:
        if not self.api_key:
            return {}

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type':  'application/json',
        }
        try:
            resp = requests.post(
                self.api_url,
                headers=headers,
                json={'message': SYSTEM_PREFIX + prompt},
                timeout=30,
            )
            if resp.status_code == 429:
                logger.error('apifreellm rate-limit (429).')
                return {'is_mock': True, '_error': 'quota_exceeded'}
            resp.raise_for_status()
            data = resp.json()
            raw  = data.get('response', '')
            # Strip any accidental markdown fences
            raw = re.sub(r'```(?:json)?', '', raw).strip().rstrip('`').strip()
            result = json.loads(raw)
            result['provider'] = 'apifreellm'
            return result
        except json.JSONDecodeError as exc:
            logger.error(f'apifreellm JSON parse error: {exc}')
            return {}
        except Exception as exc:
            logger.error(f'apifreellm call failed: {exc}')
            return {}

    def build_context(self, request_obj) -> str:
        if not request_obj:
            return ''
        try:
            return (
                f"Biznes: {request_obj.business_type} | "
                f"Tuman: {request_obj.district} | "
                f"Sarmoya: {request_obj.investment_amount} UZS\n"
            )
        except Exception:
            return ''

    # ── Block methods ────────────────────────────────────────────

    def analyze_market(self, business_type, mcc_code, district,
                       population=250000, competitor_count=12, request_obj=None) -> dict:
        prompt = self.build_context(request_obj) + (
            f"Bozor tahlili: {business_type}, {district}, "
            f"aholi {population}, raqobatchilar {competitor_count}. "
            f'JSON: {{"tam_uzs":50000000000,"sam_uzs":15000000000,"som_uzs":3000000000,'
            f'"saturation_index":0.5,"gap_score":60,"niche_opportunity_score":55,"commentary":"..."}}'
        )
        res = self._call(prompt)
        return res if res and not res.get('_error') else self._mock('A')

    def analyze_demand(self, forecast_12, p10, p50, p90,
                       synthetic_demand_score, seasonality_weekly,
                       ramazon_boost_pct, navro_boost_pct, request_obj=None) -> dict:
        prompt = self.build_context(request_obj) + (
            f"Talab tahlili: P50={p50}, ball={synthetic_demand_score}. "
            f'JSON: {{"demand_score":70,"realism_assessment":"...","commentary":"..."}}'
        )
        res = self._call(prompt)
        return res if res and not res.get('_error') else self._mock('B')

    def evaluate_location(self, lat, lng, district,
                          competitors_300m, competitors_1km, anchors, request_obj=None) -> dict:
        prompt = self.build_context(request_obj) + (
            f"Joylashuv tahlili: {district}, 300m raqobatchilar={len(competitors_300m)}. "
            f'JSON: {{"location_score":65,"anchor_effect_score":40,'
            f'"isochrone_demand_5min":3500,"isochrone_demand_10min":12000,"commentary":"..."}}'
        )
        res = self._call(prompt)
        return res if res and not res.get('_error') else self._mock('C')

    def analyze_financial_viability(self, **kwargs) -> dict:
        prompt = self.build_context(kwargs.get('request_obj')) + (
            f"Moliyaviy tahlil: sarmoya={kwargs.get('investment_uzs')}, "
            f"roi={kwargs.get('roi_12mo')}, bep={kwargs.get('bep_months')}. "
            f'JSON: {{"viability_score":65,"bep_assessment":"...","commentary":"..."}}'
        )
        res = self._call(prompt)
        return res if res and not res.get('_error') else self._mock('D')

    def analyze_competition(self, competitors, business_type,
                            district, district_churn_rate, request_obj=None) -> dict:
        prompt = self.build_context(request_obj) + (
            f"Raqobat tahlili: {business_type}, churn={district_churn_rate}%. "
            f'JSON: {{"market_risk_score":50,"district_churn_rate":15.0,'
            f'"entry_barriers":["..."],"recommendation_notes":"...","commentary":"..."}}'
        )
        res = self._call(prompt)
        return res if res and not res.get('_error') else self._mock('E')

    def final_decision(self, request_data, block_scores, composite_score) -> dict:
        prompt = (
            f"Yakuniy qaror: ball={composite_score}, bloklar={block_scores}. "
            f'JSON: {{"recommendation":"CAUTION","confidence":0.6,'
            f'"key_strengths":["..."],"key_risks":["..."],"commentary":"...","credit_tier":"Moderate"}}'
        )
        res = self._call(prompt)
        return res if res and not res.get('_error') else self._mock('FINAL')

    def analyze_hotel(self, request_obj=None) -> dict:
        res = self._call(self.build_context(request_obj) + 'Hotel tahlili. JSON: {"location_score":60,"commentary":"..."}')
        return res if res and not res.get('_error') else self._mock('HOTEL')

    def analyze_construction(self, request_obj=None) -> dict:
        res = self._call(self.build_context(request_obj) + 'Qurilish tahlili. JSON: {"cash_flow_timeline":[],"commentary":"..."}')
        return res if res and not res.get('_error') else self._mock('CONST')

    def analyze_textile(self, request_obj=None) -> dict:
        res = self._call(self.build_context(request_obj) + 'Tekstil tahlili. JSON: {"export_readiness_score":50,"commentary":"..."}')
        return res if res and not res.get('_error') else self._mock('TEXT')

    def analyze_trade(self, request_obj=None) -> dict:
        res = self._call(self.build_context(request_obj) + 'Savdo tahlili. JSON: {"working_capital_needed":0,"commentary":"..."}')
        return res if res and not res.get('_error') else self._mock('TRADE')

    def _mock(self, block: str) -> dict:
        logger.warning(f'apifreellm mock fallback for block {block}')
        return {
            'is_mock': True, 'provider': 'apifreellm (fallback)',
            'commentary': "[apifreellm xato] Zaxira ma'lumot.",
            'gap_score': 50, 'demand_score': 50, 'location_score': 50,
            'market_risk_score': 50, 'viability_score': 50, 'recommendation': 'CAUTION',
        }
