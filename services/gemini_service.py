"""
Gemini 1.5 Pro service wrapper for BiznesAI.
Handles all Gemini API calls: Block A, C, E, and final decision.
Falls back to mock data if API key is missing or call fails.
"""
import json
import logging
import time
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not installed. Using mock responses.")


class GeminiService:
    def __init__(self, api_key=None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = None
        self.model_name = None
        if GEMINI_AVAILABLE and self.api_key:
            genai.configure(api_key=self.api_key)
            self.model_name = self._resolve_model_name()
            try:
                self.model = genai.GenerativeModel(self.model_name)
            except Exception as exc:
                logger.error("Gemini model init failed (%s): %s", self.model_name, exc)
                self.model = None

    def _resolve_model_name(self) -> str:
        preferred = []
        configured = (getattr(settings, 'GEMINI_MODEL', '') or '').strip()
        if configured:
            preferred.append(configured)
        preferred.extend([
            'gemini-2.0-flash',
            'gemini-1.5-flash',
            'gemini-1.5-pro',
            'gemini-pro',
        ])

        # Keep order while de-duplicating.
        seen = set()
        ordered = [name for name in preferred if not (name in seen or seen.add(name))]
        fallback = ordered[0] if ordered else 'gemini-2.0-flash'

        try:
            models = list(genai.list_models())
            available = {
                m.name.split('/', 1)[-1]
                for m in models
                if hasattr(m, 'supported_generation_methods')
                and 'generateContent' in (m.supported_generation_methods or [])
            }
            for name in ordered:
                if name in available:
                    return name
            if available:
                return sorted(available)[0]
        except Exception as exc:
            logger.warning("Gemini list_models failed, using fallback '%s': %s", fallback, exc)

        return fallback

    def _call(self, prompt: str, temperature: float = 0.2, json_mode: bool = True) -> dict | str:
        """Core call method with retry and fallback."""
        if not self.model:
            return None  # triggers mock fallback in callers

        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json" if json_mode else "text/plain",
        )
        for attempt in range(3):
            try:
                response = self.model.generate_content(
                    prompt, generation_config=generation_config
                )
                text = response.text.strip()
                if json_mode:
                    return json.loads(text)
                return text
            except Exception as e:
                logger.error(f"Gemini attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
        return None

    # ─────────────────────────────────────────────
    # CONTEXT BUILDER — prepended to every prompt
    # ─────────────────────────────────────────────
    def build_context(self, req) -> str:
        """Build a rich Uzbek-language context block from all model fields."""
        def _f(v, default='Ko\'rsatilmagan'):
            return str(v) if v else default

        def _money(v):
            try:
                return f"{int(float(str(v))):,} UZS"
            except Exception:
                return str(v)

        return f"""SEN BANK BIZNES-TAHLIL EKSPERTISAN. O'ZBEK TILIDA JAVOB BER.

=== MIJOZ BIZNES TAVSIFI ===
{_f(req.business_description, 'Tavsif berilmagan')}

=== TUZILGAN MA\'LUMOTLAR ===
Biznes turi        : {_f(req.business_type)} (MCC: {req.mcc_code})
Kategoriya         : {req.get_business_category_display() if hasattr(req, 'get_business_category_display') else req.business_category}
Maqsadli mijoz     : {req.get_target_customer_display() if hasattr(req, 'get_target_customer_display') else req.target_customer}

Ochilish sanasi    : {_f(req.planned_opening_date)}
Ish vaqti          : {_f(req.operating_hours_start, '09:00')}–{_f(req.operating_hours_end, '21:00')}
Haftalik ish kuni  : {req.working_days_per_week} kun
Kunlik mijoz (tax) : {req.expected_daily_customers} kishi
O\'rtacha chek      : {_money(req.average_check_uzs)}
Mavsumiylik        : {'Bor: ' + req.seasonal_notes if getattr(req, 'has_seasonal_dependency', False) and getattr(req, 'seasonal_notes', '') else 'Bor' if getattr(req, 'has_seasonal_dependency', False) else 'Yo\'q'}

Manzil             : {_f(req.address_detail)}, {req.district}
Lokatsiya turi     : {req.get_location_type_display() if hasattr(req, 'get_location_type_display') else req.location_type}
Maydon             : {req.floor_area_sqm} kv.m
Mo\'ljallar         : {_f(req.nearby_landmarks)}
Avtoturargoh       : {'Bor' if req.parking_available else 'Yo\'q'}
Jamoat transport   : {'Yaqin' if req.public_transport_nearby else 'Uzoq'}

Jami investitsiya  : {_money(req.investment_amount)}
Shaxsiy kapital    : {_money(req.own_capital)}
Kredit             : {_money(req.loan_amount)}
Oylik ijara        : {_money(req.monthly_rent_uzs)}
Ish haqi fondi     : {_money(req.monthly_salary_budget)}
Xodimlar           : {req.num_employees} kishi
Kommunal           : {_money(req.monthly_utilities)}
Tovar tannarxi     : {req.cogs_percentage}%
Qaytarish muddati  : {req.desired_payback_months} oy

Ma\'lum raqobatchilar : {_f(req.known_competitors)}
Raqobat ustunligi    : {_f(req.competitor_advantage)}
Soha tajribasi       : {req.market_experience_years} yil
Oldingi muvaffaqiyat : {'Muvaffaqiyatsiz bo\'lgan' if req.previously_failed_business else 'Yo\'q'}
"""


    def analyze_market(self, business_type: str, mcc_code: str, district: str,
                       population: int = 250000, competitor_count: int = 12,
                       request_obj=None) -> dict:
        context = self.build_context(request_obj) if request_obj else ''
        prompt = context + f"""
=== A BLOKI VAZIFASI: BOZOR TAHLILI ===
Biznes turi: {business_type} | MCC: {mcc_code} | Tuman: {district}
Aholi: {population:,} kishi | Raqobatchilar: {competitor_count} ta

Faqat JSON formatida javob ber:
{{
  "tam_uzs": <umumiy bozor hajmi so'mda>,
  "sam_uzs": <xizmat ko'rsatiladigan bozor hajmi>,
  "som_uzs": <qo'lga kiritilishi mumkin bo'lgan ulush>,
  "saturation_index": <0.0-1.0, bozor to'yinganligi>,
  "gap_score": <0-100>,
  "niche_opportunity_score": <0-100>,
  "gap_analysis": "<bozor bo'shliqlar tavsifi o'zbek tilida>",
  "commentary": "<150-200 so'zlik tahlil o'zbek tilida>"
}}
Faqat JSON qaytargin.
"""
        result = self._call(prompt, temperature=0.2)
        if result:
            result.setdefault("is_mock", False)
            return result
        logger.warning("Block A: Gemini failed, using mock data")
        return self._mock_block_a(business_type, district, competitor_count)

    def _mock_block_a(self, business_type, district, competitor_count):
        base = 50_000_000_000
        sat = min(0.9, competitor_count / 20)
        gap = round((1 - sat) * 80 + 10, 1)
        niche = round(gap * 0.85, 1)
        return {
            "tam_uzs": base,
            "sam_uzs": int(base * 0.35),
            "som_uzs": int(base * 0.08),
            "saturation_index": round(sat, 2),
            "gap_score": gap,
            "niche_opportunity_score": niche,
            "gap_analysis": f"{district} tumanida {business_type} sohasida bozor bo'shliqlar mavjud.",
            "commentary": (
                f"{district} tumanida {business_type} sohasidagi bozor tahlili shuni ko'rsatadiki, "
                f"umumiy bozor hajmi katta, ammo raqobat darajasi {'yuqori' if sat > 0.6 else 'o\'rtacha'} darajada. "
                f"Nisha imkoniyatlari mavjud bo'lib, to'g'ri strategiya bilan bozorga kirish mumkin. "
                f"Mavsumiy talablar va mahalliy demografiyani hisobga olgan holda biznes ochish tavsiya etiladi. "
                f"[DEMO MA'LUMOT — Gemini API kaliti kiritilmagan]"
            ),
            "is_mock": True,
        }

    # ─────────────────────────────────────────────
    # BLOCK B — Demand Forecast (review of NumPy/Prophet output)
    # ─────────────────────────────────────────────
    def analyze_demand(self, forecast_12: list, p10: int, p50: int, p90: int,
                       synthetic_demand_score: float, seasonality_weekly: list,
                       ramazon_boost_pct: float, navro_boost_pct: float,
                       request_obj=None) -> dict:
        """
        Gemini reviews the synthetic 12-month forecast + percentiles + seasonality
        and returns a real demand assessment in Uzbek. Falls back to a synthetic
        commentary when the API is unavailable.
        """
        context = self.build_context(request_obj) if request_obj else ''
        # Show first 12 months — keep prompt compact
        forecast_text = ", ".join(f"{int(v):,}" for v in forecast_12[:12])
        prompt = context + f"""
=== B BLOKI VAZIFASI: TALAB PROGNOZINI BAHOLASH ===
Quyidagi 12 oylik daromad prognozi sintetik model (trend + mavsumiylik) yordamida hisoblangan.
Sening vazifang — uni mijozning biznes tavsifi va kontekstiga qarab BAHOLASH va REALISTIKLIGINI tekshirish.

12 oylik prognoz (UZS): [{forecast_text}]
P10 oraliq: {p10:,} UZS
P50 (mediana): {p50:,} UZS
P90 oraliq: {p90:,} UZS
Sintetik talab bali: {synthetic_demand_score:.1f}/100
Haftalik mavsumiylik (Du-Ya): {seasonality_weekly}
Ramazon ta'siri: {ramazon_boost_pct:+.1f}%
Navro'z ta'siri: {navro_boost_pct:+.1f}%
Mijozning mavsumiylik izohi: {request_obj.seasonal_notes if request_obj and getattr(request_obj, 'has_seasonal_dependency', False) and getattr(request_obj, 'seasonal_notes', '') else "Yo'q"}

Faqat JSON formatida javob ber:
{{
  "demand_score": <0-100, sening tahlilingdan keyingi yakuniy bal>,
  "realism_assessment": "<mijozning kunlik mijoz va o'rtacha chek raqamlari realistikmi? O'zbek tilida 2-3 jumla>",
  "p50_validity": "<P50 prognoz qiymati real bozor uchun mantiqiymi? O'zbek tilida 1-2 jumla>",
  "key_demand_drivers": ["<asosiy talab omili 1>", "<omil 2>", "<omil 3>"],
  "demand_risks": ["<talabga oid xavf 1>", "<xavf 2>"],
  "seasonality_warnings": "<mavsumiy tarqalishga oid ogohlantirish o'zbek tilida>",
  "commentary": "<200-250 so'zlik talab tahlili o'zbek tilida, raqamlar bilan>"
}}
Faqat JSON qaytargin.
"""
        result = self._call(prompt, temperature=0.25)
        if result:
            result.setdefault("is_mock", False)
            return result
        logger.warning("Block B: Gemini failed, using mock data")
        return self._mock_block_b(p50, synthetic_demand_score, request_obj)

    def _mock_block_b(self, p50, synthetic_demand_score, request_obj):
        bt = getattr(request_obj, 'business_type', 'biznes') if request_obj else 'biznes'
        district = getattr(request_obj, 'district', '') if request_obj else ''
        level = "yuqori" if synthetic_demand_score > 65 else ("o'rtacha" if synthetic_demand_score > 40 else "past")
        return {
            "demand_score": round(synthetic_demand_score, 1),
            "realism_assessment": (
                "Mijoz tomonidan ko'rsatilgan kunlik mijozlar soni va o'rtacha chek qiymati "
                "tanlangan biznes turi va lokatsiya uchun umumiy diapazonda turibdi."
            ),
            "p50_validity": (
                f"P50 qiymati {p50:,} UZS — bozor uchun mantiqiy diapazonda."
            ),
            "key_demand_drivers": [
                "Lokatsiyaning yo'lovchi oqimi",
                "Mijozning tanlovi va sodiqligi",
                "Mavsumiy ehtiyojlar (Ramazon, Navro'z)",
            ],
            "demand_risks": [
                "Yangi raqobatchining bozorga kirishi",
                "Iqtisodiy noaniqlik",
            ],
            "seasonality_warnings": (
                "Hafta oxiri kunlari ish kunlariga nisbatan 30-40% yuqori savdo kuzatiladi. "
                "Ramazon va Navro'z davrlari talabga sezilarli ta'sir ko'rsatadi."
            ),
            "commentary": (
                f"{district} tumanida {bt} uchun talab darajasi {level} bo'lishi kutilmoqda. "
                f"Mediana oylik daromad {p50:,} UZS atrofida bo'lib, mavsumiy tebranishlar "
                f"yil davomida ±15-20% farq qilishi mumkin. "
                f"[DEMO MA'LUMOT — Gemini API kaliti kiritilmagan]"
            ),
            "is_mock": True,
        }


    # ─────────────────────────────────────────────
    # BLOCK C — Location Intelligence
    # ─────────────────────────────────────────────
    def evaluate_location(self, lat: float, lng: float, district: str,
                         competitors_300m: list, competitors_1km: list,
                         anchors: list, request_obj=None) -> dict:
        context = self.build_context(request_obj) if request_obj else ''
        comp_text = json.dumps(competitors_300m[:5], ensure_ascii=False)
        anchor_text = json.dumps(anchors[:3], ensure_ascii=False)
        prompt = context + f"""
=== C BLOKI VAZIFASI: JOYLASHUV TAHLILI ===
Koordinatalar: {lat:.4f}, {lng:.4f} | Tuman: {district}
300m ichidagi raqobatchilar: {comp_text}
Yaqin anchor ob'ektlar: {anchor_text}
1km ichidagi raqobatchilar soni: {len(competitors_1km)}

Faqat JSON formatida javob ber:
{{
  "location_score": <0-100>,
  "anchor_effect_score": <0-100>,
  "isochrone_demand_5min": <5 daqiqalik yurishda odamlar soni>,
  "isochrone_demand_10min": <10 daqiqalik yurishda>,
  "traffic_assessment": "<joylashuv afzalliklari o'zbek tilida>",
  "commentary": "<150-200 so'zlik joylashuv tahlili o'zbek tilida>"
}}
Faqat JSON qaytargin.
"""
        result = self._call(prompt, temperature=0.2)
        if result:
            result.setdefault("is_mock", False)
            return result
        logger.warning("Block C: Gemini failed, using mock data")
        return self._mock_block_c(competitors_300m, anchors)

    def _mock_block_c(self, competitors_300m, anchors):
        c_count = len(competitors_300m)
        a_count = len(anchors)
        loc_score = max(30, min(90, 70 - c_count * 5 + a_count * 8))
        return {
            "location_score": float(loc_score),
            "anchor_effect_score": min(85.0, a_count * 25.0),
            "isochrone_demand_5min": 3500,
            "isochrone_demand_10min": 12000,
            "traffic_assessment": "Joylashuv yaxshi passajirlik oqimi bo'lgan hududda joylashgan.",
            "commentary": (
                "Tanlangan joy strategik jihatdan qulay bo'lib, yaqin atrofda yuqori passajirlik "
                "oqimi kuzatiladi. Yaqin masofada savdo markazlari, maktablar va bozorlar mavjud "
                "bo'lib, bu mijozlar oqimini ta'minlaydi. Raqobatchilar soni o'rtacha darajada. "
                "[DEMO MA'LUMOT — Gemini API kaliti kiritilmagan]"
            ),
            "is_mock": True,
        }

    # ─────────────────────────────────────────────
    # BLOCK E — Competition & Risk
    # ─────────────────────────────────────────────
    def analyze_competition(self, competitors: list, business_type: str,
                            district: str, district_churn_rate: float,
                            request_obj=None) -> dict:
        context = self.build_context(request_obj) if request_obj else ''
        comp_sample = json.dumps(competitors[:8], ensure_ascii=False)
        prompt = context + f"""
=== E BLOKI VAZIFASI: RAQOBAT VA RISK TAHLILI ===
Biznes turi: {business_type} | Tuman: {district}
Yillik biznes yopilish darajasi: {district_churn_rate:.1f}%
Raqobatchilar: {comp_sample}

Faqat JSON formatida javob ber:
{{
  "closure_probabilities": {{<raqobatchi_nomi>: <0.0-1.0>}},
  "entry_barriers": ["<to'siq 1>", "<to'siq 2>", "<to'siq 3>"],
  "market_risk_score": <0-100, 100=eng xavfli>,
  "risk_factors": ["<xavf 1>", "<xavf 2>", "<xavf 3>"],
  "recommendation_notes": "<200 so'zlik tavsiyalar o'zbek tilida>",
  "commentary": "<150 so'zlik raqobat tahlili o'zbek tilida>"
}}
Faqat JSON qaytargin.
"""
        result = self._call(prompt, temperature=0.2)
        if result:
            result.setdefault("is_mock", False)
            return result
        logger.warning("Block E: Gemini failed, using mock data")
        return self._mock_block_e(competitors, district_churn_rate)

    def _mock_block_e(self, competitors, churn_rate):
        closure_probs = {
            c.get('name', f'Raqobatchi {i+1}'): round(min(0.9, churn_rate / 100 * (1 + i * 0.1)), 2)
            for i, c in enumerate(competitors[:6])
        }
        risk_score = min(85.0, 30 + len(competitors) * 4 + churn_rate * 0.5)
        return {
            "closure_probabilities": closure_probs,
            "entry_barriers": [
                "Boshlang'ich investitsiya hajmi yuqori",
                "Mahalliy raqobatchilarning o'rnatilgan mijozlar bazasi",
                "Ruxsatnomalar va litsenziyalar olish vaqt talab etadi",
            ],
            "market_risk_score": round(risk_score, 1),
            "risk_factors": [
                "Bozor to'yinganligi xavfi",
                "Mavsumiy talabning o'zgaruvchanligi",
                "Valyuta kursi o'zgarishi ta'siri",
            ],
            "recommendation_notes": (
                "Bozorga kirish uchun differensiatsiya strategiyasi tavsiya etiladi. "
                "Raqobatchilardan farqli xizmat yoki mahsulot sifati bilan ajralib turish muhim. "
                "[DEMO MA'LUMOT — Gemini API kaliti kiritilmagan]"
            ),
            "commentary": (
                "Raqobat muhiti o'rtacha darajada bo'lib, yangi ishtirokchilar uchun imkoniyatlar mavjud. "
                "[DEMO MA'LUMOT — Gemini API kaliti kiritilmagan]"
            ),
            "is_mock": True,
        }

    # ─────────────────────────────────────────────
    # BLOCK D — Financial Viability (review of Monte Carlo output)
    # ─────────────────────────────────────────────
    def analyze_financial_viability(self, investment_uzs: float, monthly_revenue_p50: int,
                                    fixed_costs_uzs: float, cogs_pct: float,
                                    bep_months: float, bep_revenue_uzs: int,
                                    roi_12mo: float, roi_36mo: float,
                                    mc_success_probability: float,
                                    mc_mean_profit: int, mc_std_profit: int,
                                    cac_uzs: int, ltv_uzs: int, ltv_cac_ratio: float,
                                    gross_margin_pct: float,
                                    cash_flow_24mo: list,
                                    synthetic_viability_score: float,
                                    request_obj=None) -> dict:
        """
        Gemini reviews the Monte Carlo financial simulation output and produces
        an Uzbek-language viability assessment + risk warnings + final viability score.
        Falls back to a deterministic synthetic commentary on failure.
        """
        context = self.build_context(request_obj) if request_obj else ''
        # Sample cash flow to keep prompt small (every 3rd month + last)
        cf_sample = cash_flow_24mo[::3] + ([cash_flow_24mo[-1]] if cash_flow_24mo else [])
        cf_text = ", ".join(f"{int(v):,}" for v in cf_sample)

        prompt = context + f"""
=== D BLOKI VAZIFASI: MOLIYAVIY HAYOTIYLIKNI BAHOLASH ===
Quyidagi raqamlar 10,000 iteratsiyali Monte-Karlo simulyatsiyasi natijasi.
Sening vazifang — ularni mijozning tavsifi va kontekstiga qarab BAHOLASH va xavflarini aniqlash.

KIRISH RAQAMLARI:
Investitsiya: {investment_uzs:,.0f} UZS
Mediana oylik daromad (P50): {monthly_revenue_p50:,} UZS
Oylik doimiy xarajatlar: {fixed_costs_uzs:,.0f} UZS
Tovar tannarxi (COGS): {cogs_pct:.1f}%

CHIQISH NATIJALARI:
Investitsiyani qoplash muddati: {bep_months:.1f} oy
Daromad bo'yicha break-even: {bep_revenue_uzs:,} UZS/oy
12 oylik ROI: {roi_12mo:.1f}%
36 oylik ROI: {roi_36mo:.1f}%
Foyda ko'rish ehtimoli (Monte-Karlo): {mc_success_probability:.1f}%
Oylik o'rtacha foyda: {mc_mean_profit:,} UZS (σ={mc_std_profit:,})
LTV: {ltv_uzs:,} | CAC: {cac_uzs:,} | LTV/CAC: {ltv_cac_ratio:.2f}
Yalpi marja: {gross_margin_pct:.1f}%
24 oylik cash flow (har 3 oy): [{cf_text}] UZS
Sintetik viability bali: {synthetic_viability_score:.1f}/100

SQB BANK QOIDALARI (CBU 2025):
- Maksimal qarz yuki: 50% daromaddan
- DSC nisbati >= 1.25 talab etiladi
- Garov qiymati >= kreditning 125% bo'lishi kerak
- Kredit muddati 60 oygacha, foiz 24% UZS / 12% USD

Faqat JSON formatida javob ber:
{{
  "viability_score": <0-100, sening tahlilingdan keyingi yakuniy bal>,
  "bep_assessment": "<break-even muddati realistikmi va biznes turiga mos keladi mi? O'zbek tilida 2-3 jumla>",
  "roi_assessment": "<ROI ko'rsatkichlari kredit foiziga (24%) nisbatan qanday? O'zbek tilida 2 jumla>",
  "cash_flow_assessment": "<Cash flow doimiy va salbiy oylar nechta? O'zbek tilida>",
  "ltv_cac_assessment": "<LTV/CAC nisbati qoniqarli mi? O'zbek tilida 1-2 jumla>",
  "key_warnings": ["<jiddiy moliyaviy xavf 1>", "<xavf 2>", "<xavf 3>"],
  "improvement_suggestions": ["<takomillashtirish 1>", "<2>"],
  "sqb_compliance": "<SQB qoidalariga muvofiqlik holati o'zbek tilida>",
  "commentary": "<300 so'zlik yakuniy moliyaviy tahlil o'zbek tilida, raqamlar bilan>"
}}
Faqat JSON qaytargin.
"""
        result = self._call(prompt, temperature=0.25)
        if result:
            result.setdefault("is_mock", False)
            return result
        logger.warning("Block D: Gemini failed, using mock data")
        return self._mock_block_d(
            bep_months, roi_12mo, roi_36mo, mc_success_probability,
            ltv_cac_ratio, synthetic_viability_score
        )

    def _mock_block_d(self, bep_months, roi_12mo, roi_36mo, mc_success_prob,
                      ltv_cac_ratio, synthetic_viability_score):
        return {
            "viability_score": round(synthetic_viability_score, 1),
            "bep_assessment": (
                f"Investitsiyani qoplash muddati taxminan {bep_months:.1f} oy. "
                f"Bu ko'rsatkich {'qoniqarli' if bep_months < 24 else 'uzoq'} hisoblanadi."
            ),
            "roi_assessment": (
                f"12 oylik ROI: {roi_12mo:.1f}%, 36 oylik: {roi_36mo:.1f}%. "
                f"Bu ko'rsatkichlar bank kredit foiziga (24%) nisbatan "
                f"{'ijobiy' if roi_12mo > 24 else 'past'} darajada."
            ),
            "cash_flow_assessment": "Oylik cash flow umumiy o'sish trendiga ega.",
            "ltv_cac_assessment": (
                f"LTV/CAC nisbati {ltv_cac_ratio:.2f} bo'lib, "
                f"{'yaxshi' if ltv_cac_ratio > 3 else 'qoniqarli' if ltv_cac_ratio > 1 else 'past'} darajada."
            ),
            "key_warnings": [
                "Daromad oqimining mavsumiy o'zgarishi",
                "Doimiy xarajatlarning yuqoriligi",
                "Boshlang'ich aylanma kapital yetishmasligi xavfi",
            ],
            "improvement_suggestions": [
                "Doimiy xarajatlarni 10-15% qisqartirish imkoniyatini ko'rib chiqish",
                "Marja oshirish uchun premium mahsulot/xizmat liniyasi qo'shish",
            ],
            "sqb_compliance": "Hozirgi raqamlar SQB qoidalariga umumiy muvofiq.",
            "commentary": (
                f"Moliyaviy tahlil shuni ko'rsatadiki, investitsiyaning qoplanish muddati "
                f"taxminan {bep_months:.1f} oy. Monte-Karlo simulatsiyasi asosida foyda ko'rish "
                f"ehtimoli {mc_success_prob:.1f}%. 12 oylik ROI: {roi_12mo:.1f}%, "
                f"36 oylik ROI: {roi_36mo:.1f}%. LTV/CAC nisbati {ltv_cac_ratio:.1f} bo'lib, "
                f"{'yaxshi' if ltv_cac_ratio > 3 else 'qoniqarli'} darajada. "
                f"[DEMO MA'LUMOT — Gemini API kaliti kiritilmagan]"
            ),
            "is_mock": True,
        }


    # ─────────────────────────────────────────────
    # FINAL DECISION
    # ─────────────────────────────────────────────
    def final_decision(self, request_data: dict, block_scores: dict,
                       composite_score: float) -> dict:
        prompt = f"""
Siz bank kredit tahlilchisisiz. Quyidagi ma'lumotlar asosida yakuniy xulosa chiqaring.

Biznes: {request_data['business_type']} — {request_data['district']} tumani
Investitsiya: {request_data['investment_amount']:,} so'm
Kompozit ball: {composite_score:.1f}/100

Bloklar ballari:
- A (Bozor tahlili): {block_scores.get('A', 0):.1f}/100
- B (Talab prognozi): {block_scores.get('B', 0):.1f}/100
- C (Joylashuv): {block_scores.get('C', 0):.1f}/100
- D (Moliyaviy): {block_scores.get('D', 0):.1f}/100
- E (Raqobat): {block_scores.get('E', 0):.1f}/100

JSON formatida javob bering:
{{
  "recommendation": "<HA yoki YO'Q yoki EHTIYOT>",
  "confidence": <0.0 dan 1.0 gacha>,
  "key_strengths": ["<kuchli tomon 1>", "<kuchli tomon 2>"],
  "key_risks": ["<xavf 1>", "<xavf 2>"],
  "commentary": "<300 so'zlik yakuniy tahlil o'zbek tilida, aniq tavsiyalar bilan>",
  "credit_tier": "<Excellent / Good / Moderate / High Risk>"
}}

Javobni o'zbek tilida ber. Faqat JSON qaytargin.
"""
        result = self._call(prompt, temperature=0.4)
        if result:
            result.setdefault("is_mock", False)
            return result
        logger.warning("Final decision: Gemini failed, using rule-based fallback")
        return self._mock_final(composite_score)

    def _mock_final(self, composite_score: float) -> dict:
        if composite_score >= 70:
            rec, tier = 'HA', 'Good'
            commentary = (
                f"Kompozit ball {composite_score:.1f}/100 bo'lib, biznes ochish uchun sharoitlar qulay. "
                "Bozor tahlili, joylashuv va moliyaviy ko'rsatkichlar ijobiy natijalar ko'rsatmoqda. "
                "Investitsiyani amalga oshirish tavsiya etiladi, ammo moliyaviy ehtiyotkorlik zarur. "
                "[DEMO MA'LUMOT — Gemini API kaliti kiritilmagan]"
            )
        elif composite_score >= 45:
            rec, tier = 'CAUTION', 'Moderate'
            commentary = (
                f"Kompozit ball {composite_score:.1f}/100 bo'lib, bir qancha xavf omillari mavjud. "
                "Biznesni boshlashdan oldin qo'shimcha tadqiqot o'tkazish va kapital miqdorini "
                "ko'rib chiqish tavsiya etiladi. Ehtiyotkorlik bilan yondashish kerak. "
                "[DEMO MA'LUMOT — Gemini API kaliti kiritilmagan]"
            )
        else:
            rec, tier = 'NO', 'High Risk'
            commentary = (
                f"Kompozit ball {composite_score:.1f}/100 bo'lib, ko'plab salbiy omillar aniqlandi. "
                "Hozirgi sharoitda bu biznesni bu joyda ochish tavsiya etilmaydi. "
                "Joylashuvni yoki biznes turini qayta ko'rib chiqish tavsiya etiladi. "
                "[DEMO MA'LUMOT — Gemini API kaliti kiritilmagan]"
            )
        return {
            "recommendation": rec,
            "confidence": 0.72,
            "key_strengths": ["Bozor hajmi yetarli", "Joylashuv qulayligi"],
            "key_risks": ["Raqobat darajasi", "Mavsumiy tarqalish"],
            "commentary": commentary,
            "credit_tier": tier,
            "is_mock": True,
        }

    # ══════════════════════════════════════════════════════════════
    # CATEGORY METHODS
    # ══════════════════════════════════════════════════════════════

    def analyze_hotel(self, req) -> dict:
        """H1+H2+H3: location score, RevPAR forecast, SQB verdict for hotels."""
        ctx = self.build_context(req)
        try:
            detail = req.hotel_detail
        except Exception:
            detail = None

        if detail:
            rooms = detail.total_rooms
            low   = float(detail.room_rate_low_usd)
            high  = float(detail.room_rate_high_usd)
            occ   = detail.target_occupancy_pct / 100
            avg_r = (low + high) / 2
            usd_rate = 12700  # approximate UZS/USD

            # Seasonal occupancy pattern (Uzbekistan)
            seasonal_occ = [0.55,0.55,0.72,0.82,0.85,0.88,0.90,0.90,0.80,0.75,0.60,0.50]
            seasonal_rate_mult = [0.85,0.85,1.0,1.1,1.1,1.15,1.2,1.2,1.1,1.05,0.9,0.85]
            tourist_flow = [int(rooms * seasonal_occ[m] * 30) for m in range(12)]
            revpar       = [round(avg_r * seasonal_occ[m] * seasonal_rate_mult[m], 1) for m in range(12)]
            monthly_rev  = [int(rooms * revpar[m] * 30 * usd_rate) for m in range(12)]

            loc_score = 100.0
            if detail.distance_to_airport_km > 30: loc_score -= 20
            elif detail.distance_to_airport_km > 15: loc_score -= 10
            if detail.distance_to_top_attraction_km > 5: loc_score -= 20
            elif detail.distance_to_top_attraction_km > 2: loc_score -= 10
            if detail.franchise_agreement: loc_score += 10
            loc_score = max(0, min(100, loc_score))
            tariff_cfg = detail.booking_platforms if isinstance(detail.booking_platforms, dict) else {}
            tariff_system = tariff_cfg.get("tariff_system", "seasonal")
            extra_tariff_label = tariff_cfg.get("extra_tariff_label", "")
            extra_tariff_value = float(tariff_cfg.get("extra_tariff_value_usd") or 0)
            has_known_competitors = bool(getattr(req, "known_competitors", "").strip())

            mock = {
                "location_score": loc_score,
                "tourist_flow_monthly": tourist_flow,
                "occupancy_forecast": [round(seasonal_occ[m]*100, 1) for m in range(12)],
                "revpar_forecast": revpar,
                "monthly_revenue_forecast": monthly_rev,
                "revenue_p50_usd": round(sum(revpar) / 12 * rooms * 30, 0),
                "seasonality_notes": "Samarqand/Buxoro: aprel-oktyabr yuqori sezon. Qishda 40-55% band.",
                "risk_flags": (
                    ["Aeroportdan uzoqlik (>30km)"] if detail.distance_to_airport_km > 30 else []
                ) + (
                    ["Yaqin raqobatchilar mavjud"] if has_known_competitors else []
                ),
                "subsidy_eligible": detail.applying_for_subsidy,
                "credit_structure_recommendation": (
                    "6-12 oylik imtiyozli davr tavsiya etiladi (qurilish/remont bosqichi). "
                    "Kredit muddati: 60 oy. " +
                    ("VM 550/2024 subsidiyasi: foiz stavkasi 5.6% gacha pasayishi mumkin." if detail.applying_for_subsidy else "")
                ),
                "ai_commentary": (
                    f"{detail.hotel_name or 'Mehmonxona'} uchun taxminiy oylik RevPAR: ${sum(revpar)/12:.0f}. "
                    f"Joylashuv bali: {loc_score:.0f}/100. "
                    f"Yillik o'rtacha band bo'lish: {sum(seasonal_occ)/12*100:.0f}%. "
                    f"Tarif tizimi: {tariff_system}. "
                    + (f"Qo'shimcha tarif: {extra_tariff_label} (${extra_tariff_value:.0f}). " if extra_tariff_label else "")
                    + "[Hisob-kitob ma'lumoti — AI demo rejim]"
                ),
                "is_mock": True,
            }
        else:
            mock = {"location_score": 50.0, "tourist_flow_monthly": [100]*12,
                    "occupancy_forecast": [60.0]*12, "revpar_forecast": [50.0]*12,
                    "monthly_revenue_forecast": [30_000_000]*12, "revenue_p50_usd": 1500.0,
                    "risk_flags": [], "subsidy_eligible": False, "is_mock": True,
                    "credit_structure_recommendation": "", "ai_commentary": "Ma'lumot yetarli emas."}

        if not self.model:
            return mock

        prompt = f"""{ctx}

Siz SQB bank eksperti sifatida mehmonxona biznesini baholaysiz.

HOTEL MA'LUMOTLARI:
- Xonalar: {getattr(detail,'total_rooms',20)}, Shahar: {getattr(detail,'city','tashkent')}
- Narx: ${getattr(detail,'room_rate_low_usd',40)}-${getattr(detail,'room_rate_high_usd',80)}/kecha
- Aeroportgacha: {getattr(detail,'distance_to_airport_km',20)}km
- Diqqatgohgacha: {getattr(detail,'distance_to_top_attraction_km',2)}km

Quyidagi JSON formatida javob bering:
{{
  "location_score": <0-100>,
  "tourist_flow_monthly": [<12 ta son>],
  "occupancy_forecast": [<12 ta foiz>],
  "revpar_forecast": [<12 ta USD narx>],
  "risk_flags": ["..."],
  "subsidy_eligible": true/false,
  "credit_structure_recommendation": "...",
  "ai_commentary": "..."
}}"""
        result = self._call(prompt)
        if not result:
            return mock
        mock.update(result)
        mock["is_mock"] = False
        return mock

    def analyze_construction(self, req) -> dict:
        """C1+C2+C3: 60-month cash flow timeline + market analysis for construction."""
        ctx = self.build_context(req)
        try:
            detail = req.construction_detail
        except Exception:
            detail = None

        loan = float(req.loan_amount or 0)
        term = float(getattr(detail, 'loan_term_months', 60) if detail else 60)
        monthly_payment = (loan / term) * (1 + 0.24/12 * term / 2) / term * term if term > 0 else 0
        monthly_payment = loan * 0.024  # simple ~24% annual / 12 months rough

        ttfi = getattr(detail, 'months_to_first_income', 6) if detail else 6
        margin = getattr(detail, 'average_margin_pct', 18.0) if detail else 18.0
        contract_size = float(getattr(detail, 'expected_first_contract_size_uzs', 50_000_000) if detail else 50_000_000)
        fixed = float(req.computed_monthly_fixed_costs)

        # Build 60-month cash flow
        cf = []
        cumulative = 0
        breakeven_month = None
        for m in range(60):
            if m < ttfi:
                revenue = 0.0
            elif m < 18:
                revenue = contract_size * margin / 100 * 0.5
            elif m < 36:
                revenue = contract_size * margin / 100
            else:
                revenue = contract_size * margin / 100 * 1.3
            net = revenue - fixed - monthly_payment
            cumulative += net
            cf.append(round(net, 0))
            if breakeven_month is None and cumulative > 0 and m >= ttfi:
                breakeven_month = m + 1

        risk = "XAVFLI" if ttfi > 12 else ("O'RTACHA" if ttfi > 6 else "YAXSHI")

        mock = {
            "cash_flow_timeline": cf,
            "cumulative_cash_flow": [sum(cf[:i+1]) for i in range(60)],
            "monthly_loan_payment": monthly_payment,
            "breakeven_month": breakeven_month,
            "faza_1_risk": risk,
            "faza_2_risk": "O'RTACHA" if ttfi <= 8 else "XAVFLI",
            "faza_3_risk": "YAXSHI",
            "license_risk_flag": not getattr(detail, 'has_license', False) if detail else True,
            "contract_pipeline_score": 60.0 if (detail and detail.current_contracts) else 30.0,
            "market_size_uzs": 50_000_000_000,
            "tender_opportunity_score": 55.0,
            "ai_commentary": (
                f"Birinchi daromadgacha {ttfi} oy. "
                f"Kredit to'lovi oyiga ~{monthly_payment:,.0f} UZS. "
                f"O'rtacha marj {margin}%. Faza-1 riski: {risk}. "
                "[Demo hisob-kitob]"
            ),
            "is_mock": True,
        }

        if not self.model:
            return mock

        prompt = f"""{ctx}

Qurilish biznesini SQB kredit nuqtai nazaridan baholang.
Litsenziya: {getattr(detail,'has_license',False)}, Birinchi daromad: {ttfi} oy,
Marj: {margin}%, Kredit to'lovi: {monthly_payment:,.0f} UZS/oy.

JSON javob:
{{
  "faza_1_risk": "XAVFLI|O'RTACHA|YAXSHI",
  "license_risk_flag": true/false,
  "contract_pipeline_score": <0-100>,
  "market_size_uzs": <son>,
  "ai_commentary": "..."
}}"""
        result = self._call(prompt)
        if result:
            mock.update(result)
            mock["is_mock"] = False
        return mock

    def analyze_textile(self, req) -> dict:
        """T1+T2+T3: export readiness score + web-search market data for textile."""
        try:
            detail = req.textile_detail
        except Exception:
            detail = None

        certs = list(getattr(detail, 'certifications', []) or [])
        export_exp = getattr(detail, 'export_experience', False) if detail else False
        buyers = getattr(detail, 'existing_buyers', '') if detail else ''
        markets = list(getattr(detail, 'target_market', []) or [])
        mach_age = getattr(detail, 'machinery_age_years', 5) if detail else 5

        # Export readiness scoring
        cert_score = 30 if ('gots' in certs or 'oeko_tex' in certs) else \
                     18 if ('iso_9001' in certs or 'bci' in certs) else \
                     8 if (certs and 'none' not in certs) else 0
        buyer_score = 25 if export_exp else 0
        buyer_score += 20 if (buyers and len(buyers) > 20) else 0
        market_score = 15 if ({'eu','us','middle_east'} & set(markets)) else \
                       8 if ({'cis'} & set(markets)) else 0
        equip_score = 10 if mach_age <= 5 else 5 if mach_age <= 10 else 0
        export_readiness = min(100, cert_score + buyer_score + market_score + equip_score)

        interp = ("Eksport uchun tayyor" if export_readiness >= 70 else
                  "6-12 oylik tayyorgarlik kerak" if export_readiness >= 40 else
                  "Avval mahalliy bozordan boshlash tavsiya etiladi")

        mock = {
            "export_readiness_score": export_readiness,
            "certification_score": cert_score,
            "buyer_network_score": min(100, buyer_score),
            "market_access_score": market_score,
            "certification_risk_flag": export_readiness < 30,
            "readiness_interpretation": interp,
            "market_research_data": {
                "uzbekistan_textile_export_usd_2024": 2_800_000_000,
                "top_export_markets": ["Rossiya 38%", "Xitoy 18%", "Turkiya 12%", "Qozog'iston 8%"],
                "gots_cert_cost_usd": 5000,
                "gots_cert_months": 6,
                "eu_gsp_status": "O'zbekiston GSP+ imtiyozidan foydalanadi",
            },
            "export_contract_bonus": bool(buyers and len(buyers) > 20),
            "free_zone_eligible": True,
            "ai_commentary": (
                f"Eksport tayyorlik bali: {export_readiness}/100. {interp}. "
                f"O'zbekiston tekstil eksporti 2024: ~$2.8 mlrd. "
                f"{'GOTS sertifikati mavjud — EU bozori ochiq.' if 'gots' in certs else 'GOTS sertifikati tavsiya etiladi (EU bozori uchun).'} "
                "[Demo ma'lumot]"
            ),
            "is_mock": True,
        }

        if not self.model:
            return mock

        prompt = f"""{self.build_context(req)}

Tekstil biznesini eksport tayyor baholash va SQB kredit tahlili.
Sertifikatlar: {certs}, Eksport tajribasi: {export_exp}, Bozorlar: {markets}.

O'zbekiston tekstil eksporti haqida ma'lumot bering va JSON qaytaring:
{{
  "export_readiness_score": <0-100>,
  "readiness_interpretation": "...",
  "market_research_data": {{"key": "val"}},
  "ai_commentary": "..."
}}"""
        result = self._call(prompt)
        if result:
            mock.update(result)
            mock["is_mock"] = False
        return mock

    def analyze_trade(self, req) -> dict:
        """S1+S2+S3: working capital analysis + location footfall for trade/retail."""
        try:
            detail = req.trade_detail
        except Exception:
            detail = None

        stock = float(getattr(detail, 'avg_monthly_stock_uzs', 10_000_000) if detail else 10_000_000)
        markup = float(getattr(detail, 'avg_markup_pct', 25.0) if detail else 25.0)
        inv_days = int(getattr(detail, 'inventory_turnover_days', 30) if detail else 30)
        sup_days = int(getattr(detail, 'supplier_credit_days', 14) if detail else 14)
        competitors = int(getattr(detail, 'direct_competitors_300m', 2) if detail else 2)
        foot = getattr(detail, 'foot_traffic', 'medium') if detail else 'medium'

        wc_needed  = stock * (inv_days / 30)
        sup_float  = stock * (sup_days / 30)
        wc_gap     = wc_needed - sup_float
        monthly_rev = stock * (1 + markup / 100)
        gross_profit = stock * (markup / 100)

        ft_score = {'very_high': 90, 'high': 70, 'medium': 50, 'low': 25}.get(foot, 50)
        comp_score = max(0, 80 - competitors * 15)
        loc_score = (ft_score * 0.6 + comp_score * 0.4)

        mock = {
            "working_capital_needed": int(wc_needed),
            "supplier_float": int(sup_float),
            "net_working_capital_gap": int(wc_gap),
            "monthly_revenue_estimate": int(monthly_rev),
            "gross_profit_monthly": int(gross_profit),
            "location_foot_traffic_score": ft_score,
            "competitor_density_score": comp_score,
            "overall_location_score": round(loc_score, 1),
            "recommended_loan_type": "Aylanma kapital krediti",
            "recommended_term_months": 24 if inv_days <= 30 else 36,
            "ai_commentary": (
                f"Aylanma kapital: {wc_needed:,.0f} UZS kerak, "
                f"yetkazib beruvchi {sup_days} kun kredit beradi ({sup_float:,.0f} UZS). "
                f"Sof kamomad: {wc_gap:,.0f} UZS. "
                f"Joylashuv bali: {loc_score:.0f}/100 ({foot} oqim). "
                "[Demo hisob-kitob]"
            ),
            "is_mock": True,
        }

        if not self.model:
            return mock

        prompt = f"""{self.build_context(req)}

Savdo biznesini SQB kredit nuqtai nazaridan baholang.
Tovar zaxira: {stock:,.0f} UZS, Ustama: {markup}%, Aylanma: {inv_days} kun.

JSON:
{{
  "overall_location_score": <0-100>,
  "recommended_loan_type": "...",
  "recommended_term_months": <son>,
  "ai_commentary": "..."
}}"""
        result = self._call(prompt)
        if result:
            mock.update(result)
            mock["is_mock"] = False
        return mock
