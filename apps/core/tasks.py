"""
Celery tasks for all 5 analysis blocks + orchestrator.
Chord pattern: A+B+C parallel → D → E → final_decision
"""
import logging
import numpy as np
from celery import shared_task, group, chain, chord
from django.utils import timezone

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# COMPARISON ENGINE — user assumptions vs AI reality
# ══════════════════════════════════════════════════════════════

def _compare(user_val: float, ai_val: float, label: str) -> dict:
    """Return a structured diff between user assumption and AI estimate."""
    if ai_val and ai_val != 0:
        diff_pct = ((user_val - ai_val) / abs(ai_val)) * 100
    else:
        diff_pct = 0.0
    abs_diff = abs(diff_pct)
    risk = 'low' if abs_diff <= 20 else ('medium' if abs_diff <= 50 else 'high')
    return {
        'label':    label,
        'user':     round(user_val),
        'ai':       round(ai_val),
        'diff_pct': round(diff_pct, 1),
        'risk':     risk,
    }


# ══════════════════════════════════════════════════════════════
# VALIDATION RULES — per block, returns issues + error count
# ══════════════════════════════════════════════════════════════

def _validate_block_a(block_a) -> dict:
    """
    Block A (Market Analysis) validation rules.
    Thresholds:
      • saturation_index > 0.80  → warning (> 0.95 → error)
      • niche_opportunity_score < 30 → error
      • som_uzs < 2 B UZS       → warning
      • gap_score < 25           → warning
    """
    issues = []

    if block_a.saturation_index > 0.95:
        issues.append({'level': 'error', 'code': 'EXTREME_SATURATION',
            'message': f"Bozor haddan tashqari to'yingan "
                       f"({block_a.saturation_index:.0%}). Kirish imkonsiz."})
    elif block_a.saturation_index > 0.80:
        issues.append({'level': 'warning', 'code': 'HIGH_SATURATION',
            'message': f"Bozor to'yingan ({block_a.saturation_index:.0%}). "
                       f"Raqobat juda yuqori — differensiatsiya zarur."})

    if block_a.niche_opportunity_score < 30:
        issues.append({'level': 'error', 'code': 'LOW_OPPORTUNITY',
            'message': f"Niche imkoniyati bali juda past "
                       f"({block_a.niche_opportunity_score:.0f}/100). "
                       f"Bozorga kirish qiyin."})

    if block_a.som_uzs < 2_000_000_000:
        issues.append({'level': 'warning', 'code': 'LOW_SOM',
            'message': f"SOM juda kichik "
                       f"({block_a.som_uzs / 1e9:.1f} mlrd so'm). "
                       f"Maqsadli bozor yetarli daromad ta'minlamasligi mumkin."})

    if block_a.gap_score < 25:
        issues.append({'level': 'warning', 'code': 'LOW_GAP_SCORE',
            'message': "GAP tahlili: bozorda bo'sh joy topilmadi. "
                       "Mavjud raqobatchilar barcha segmentlarni qoplagan."})

    return {
        'issues':      issues,
        'error_count': sum(1 for i in issues if i['level'] == 'error'),
        'warn_count':  sum(1 for i in issues if i['level'] == 'warning'),
    }


def _validate_block_b(block_b) -> dict:
    """
    Block B (Demand Forecast) validation rules.
    Thresholds:
      • demand_score < 30         → error
      • demand_score < 45         → warning
      • declining 12-mo trend     → warning
      • very wide confidence band → warning
    """
    issues = []

    if block_b.demand_score < 30:
        issues.append({'level': 'error', 'code': 'VERY_LOW_DEMAND',
            'message': f"Talab juda past (ball: {block_b.demand_score:.0f}/100). "
                       f"Prognoz salbiy yoki kritik darajada past."})
    elif block_b.demand_score < 45:
        issues.append({'level': 'warning', 'code': 'LOW_DEMAND',
            'message': f"Talab o'rtachadan past (ball: {block_b.demand_score:.0f}/100). "
                       f"Daromad maqsad ko'rsatkichlardan pastda bo'lishi mumkin."})

    forecast = block_b.monthly_forecast_12 or []
    if len(forecast) >= 6:
        early_avg = sum(forecast[:3]) / 3
        late_avg  = sum(forecast[-3:]) / 3
        if early_avg > 0 and late_avg < early_avg * 0.85:
            issues.append({'level': 'warning', 'code': 'DECLINING_TREND',
                'message': "12 oylik prognozda pasayish trendi kuzatildi. "
                           "Daromad vaqt o'tishi bilan kamayishi kutilmoqda."})

    p10 = block_b.revenue_p10 or 0
    p50 = block_b.revenue_p50 or 1
    if p10 > 0 and p50 / p10 > 4:
        issues.append({'level': 'warning', 'code': 'HIGH_UNCERTAINTY',
            'message': "Daromad prognozida katta noaniqlik (P90/P10 > 4x). "
                       "Moliyaviy reja konservativ versiyaga asoslanishi kerak."})

    return {
        'issues':      issues,
        'error_count': sum(1 for i in issues if i['level'] == 'error'),
        'warn_count':  sum(1 for i in issues if i['level'] == 'warning'),
    }


def _validate_block_c(block_c) -> dict:
    """
    Block C (Location Intelligence) validation rules.
    Thresholds:
      • location_score < 35       → error
      • location_score < 50       → warning
      • competitors_300m >= 5     → error
      • anchor_effect_score < 25  → warning
    """
    issues = []

    if block_c.location_score < 35:
        issues.append({'level': 'error', 'code': 'VERY_LOW_LOCATION',
            'message': f"Joylashuv bali juda past ({block_c.location_score:.0f}/100). "
                       f"Trafik va mavjudlik jiddiy muammo."})
    elif block_c.location_score < 50:
        issues.append({'level': 'warning', 'code': 'LOW_LOCATION',
            'message': f"Joylashuv bali o'rtachadan past ({block_c.location_score:.0f}/100). "
                       f"Qo'shimcha marketing strategiyasi zarur."})

    n_300 = len(block_c.competitors_300m or [])
    if n_300 >= 5:
        issues.append({'level': 'error', 'code': 'TOO_MANY_NEARBY_COMPS',
            'message': f"300 metr ichida {n_300} ta to'g'ridan-to'g'ri raqobatchi — "
                       f"juda yuqori raqobat zichligi."})

    if block_c.anchor_effect_score < 25:
        issues.append({'level': 'warning', 'code': 'LOW_ANCHOR_EFFECT',
            'message': "Yaqin atrofda yirik attraktorlar (bozor, maktab, kasalxona) topilmadi. "
                       "Spontan mijozlar kamroq bo'ladi."})

    return {
        'issues':      issues,
        'error_count': sum(1 for i in issues if i['level'] == 'error'),
        'warn_count':  sum(1 for i in issues if i['level'] == 'warning'),
    }


def _validate_block_d(block_d) -> dict:
    """
    Block D (Financial Viability) validation rules.
    Thresholds:
      • mc_success_probability < 40  → error
      • mc_success_probability < 55  → warning
      • breakeven_months > 48        → error
      • breakeven_months > 36        → warning
      • roi_12mo < 0                 → error
      • ltv_cac_ratio < 1.0         → warning
      • last 6 months of CF all < 0  → error
    """
    issues = []

    if block_d.mc_success_probability < 40:
        issues.append({'level': 'error', 'code': 'LOW_SUCCESS_PROB',
            'message': f"Monte Carlo muvaffaqiyat ehtimoli "
                       f"{block_d.mc_success_probability:.0f}% (< 40%). "
                       f"Ko'p simulyatsiyalarda zarar kutilmoqda."})
    elif block_d.mc_success_probability < 55:
        issues.append({'level': 'warning', 'code': 'MARGINAL_SUCCESS_PROB',
            'message': f"Muvaffaqiyat ehtimoli {block_d.mc_success_probability:.0f}% — "
                       f"chegaraviy daraja. Xarajatlarni kamaytirish tavsiya etiladi."})

    if block_d.breakeven_months > 48:
        issues.append({'level': 'error', 'code': 'VERY_LONG_BEP',
            'message': f"Tannarx qoplash muddati {block_d.breakeven_months:.0f} oy (> 48). "
                       f"Investitsiya qaytimi juda uzoq."})
    elif block_d.breakeven_months > 36:
        issues.append({'level': 'warning', 'code': 'LONG_BEP',
            'message': f"Tannarx qoplash muddati {block_d.breakeven_months:.0f} oy (> 36). "
                       f"SQB kredit muddatidan oshishi mumkin."})

    if block_d.roi_12mo < 0:
        issues.append({'level': 'error', 'code': 'NEGATIVE_ROI',
            'message': f"12 oylik ROI salbiy ({block_d.roi_12mo:.1f}%). "
                       f"Birinchi yilda zarar kutilmoqda."})

    ltv_cac = block_d.ltv_cac_ratio or 0
    if 0 < ltv_cac < 1.0:
        issues.append({'level': 'warning', 'code': 'POOR_LTV_CAC',
            'message': f"LTV/CAC = {ltv_cac:.2f} (1 dan past). "
                       f"Mijoz jalb qilish xarajati uning umr boylik qiymatidan yuqori."})

    cf = block_d.cash_flow_monthly_24 or []
    if len(cf) >= 6 and all(v < 0 for v in cf[-6:]):
        issues.append({'level': 'error', 'code': 'PERSISTENT_NEGATIVE_CF',
            'message': "Oxirgi 6 oylik pul oqimi doimo salbiy. "
                       "Loyiha 24 oy ichida daromadga chiqmaydi."})

    return {
        'issues':      issues,
        'error_count': sum(1 for i in issues if i['level'] == 'error'),
        'warn_count':  sum(1 for i in issues if i['level'] == 'warning'),
    }


def _validate_block_e(block_e) -> dict:
    """
    Block E (Competition & Risk) validation rules.
    Thresholds:
      • market_risk_score > 75  → error
      • market_risk_score > 60  → warning
      • district_churn_rate > 35 → warning
      • competitors_300m >= 6   → error
    """
    issues = []

    if block_e.market_risk_score > 75:
        issues.append({'level': 'error', 'code': 'VERY_HIGH_MARKET_RISK',
            'message': f"Bozor xavf bahosi {block_e.market_risk_score:.0f}/100 — "
                       f"juda xavfli. Ko'plab raqobatchilar va yuqori yopilish ehtimoli."})
    elif block_e.market_risk_score > 60:
        issues.append({'level': 'warning', 'code': 'HIGH_MARKET_RISK',
            'message': f"Bozor xavf bahosi {block_e.market_risk_score:.0f}/100 — "
                       f"yuqori. Xavf boshqaruv strategiyasi zarur."})

    if block_e.district_churn_rate > 35:
        issues.append({'level': 'warning', 'code': 'HIGH_CHURN_RATE',
            'message': f"Tumandagi yillik yopilish koeffitsienti "
                       f"{block_e.district_churn_rate:.0f}% — yuqori. "
                       f"Ushbu tuman uchun biznes baquvvatligi pastroq."})

    n_300 = len(block_e.competitors_300m or [])
    if n_300 >= 6:
        issues.append({'level': 'error', 'code': 'SEVERE_COMPETITION',
            'message': f"300 metr ichida {n_300} ta raqobatchi — "
                       f"jiddiy raqobat. Bozorga kirish juda qiyin."})

    return {
        'issues':      issues,
        'error_count': sum(1 for i in issues if i['level'] == 'error'),
        'warn_count':  sum(1 for i in issues if i['level'] == 'warning'),
    }


def _save_validation(block_obj, validation: dict):
    """Attach validation results to a block's raw_data and persist."""
    try:
        raw = block_obj.raw_data or {}
        raw['validation'] = validation
        block_obj.raw_data = raw
        block_obj.save(update_fields=['raw_data'])
    except Exception as exc:
        logger.warning(f"Failed to save validation for {block_obj}: {exc}")


def _collect_all_validations(block_a, block_b, block_c, block_d, block_e) -> dict:
    """Aggregate all validation issues from every block for the final decision."""
    all_errors, all_warnings = [], []
    for block, letter in [(block_a, 'A'), (block_b, 'B'),
                          (block_c, 'C'), (block_d, 'D'), (block_e, 'E')]:
        if not block:
            continue
        raw = getattr(block, 'raw_data', None) or {}
        for issue in (raw.get('validation') or {}).get('issues', []):
            entry = f"[{letter}] {issue['message']}"
            if issue['level'] == 'error':
                all_errors.append(entry)
            else:
                all_warnings.append(entry)
    return {'errors': all_errors, 'warnings': all_warnings}


def run_analysis_sync(request_id: int):
    """
    Sequential (non-Celery) runner used when USE_CELERY=False.
    Runs A → B → C → D → E → final_decision in a background thread.
    """
    from apps.core.models import BusinessAnalysisRequest
    try:
        req = BusinessAnalysisRequest.objects.get(pk=request_id)
        req.status = 'processing'
        req.progress_pct = 5
        req.completed_blocks = []
        req.save(update_fields=['status', 'progress_pct', 'completed_blocks'])

        task_block_a.apply(args=(request_id,))
        task_block_b.apply(args=(request_id,))
        task_block_c.apply(args=(request_id,))
        task_block_d.apply(args=(None, request_id))
        task_block_e.apply(args=(None, request_id))
        task_final_decision.apply(args=(None, request_id))

        cat = getattr(req, 'business_category_type', '')
        cat_task_map = {
            'hotel':        task_category_hotel,
            'construction': task_category_construction,
            'textile':      task_category_textile,
            'trade':        task_category_trade,
        }
        cat_task = cat_task_map.get(cat)
        if cat_task:
            cat_task.apply(args=(request_id,))

    except Exception as exc:
        logger.exception(f"Sync analysis failed for request {request_id}")
        try:
            from apps.core.models import BusinessAnalysisRequest
            req = BusinessAnalysisRequest.objects.get(pk=request_id)
            req.status = 'failed'
            req.warning_message = str(exc)
            req.save(update_fields=['status', 'warning_message'])
        except Exception:
            pass


def _get_request(request_id: int):
    from apps.core.models import BusinessAnalysisRequest
    return BusinessAnalysisRequest.objects.get(pk=request_id)


def _mark_block_done(request, block_letter: str, progress_step: int):
    completed = request.completed_blocks or []
    if block_letter not in completed:
        completed.append(block_letter)
    request.completed_blocks = completed
    request.progress_pct = min(95, request.progress_pct + progress_step)
    request.save(update_fields=['completed_blocks', 'progress_pct'])


# ══════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def run_full_analysis(self, request_id: int):
    """
    Orchestrator: A+B+C in parallel, then D, then E, then final_decision.
    Category-specific tasks run after the standard chain completes.
    """
    try:
        req = _get_request(request_id)
        req.status = 'processing'
        req.progress_pct = 5
        req.completed_blocks = []
        req.save(update_fields=['status', 'progress_pct', 'completed_blocks'])

        # Category-specific task (appended to chain end)
        cat = getattr(req, 'business_category_type', 'general')
        cat_task_map = {
            'hotel':        task_category_hotel,
            'construction': task_category_construction,
            'textile':      task_category_textile,
            'trade':        task_category_trade,
        }
        cat_task = cat_task_map.get(cat)

        if cat_task:
            final_chain = chain(
                task_block_d.s(request_id),
                task_block_e.s(request_id),
                task_final_decision.s(request_id),
                cat_task.si(request_id),      # si = immutable sig (ignores prev result)
            )
        else:
            final_chain = chain(
                task_block_d.s(request_id),
                task_block_e.s(request_id),
                task_final_decision.s(request_id),
            )

        workflow = chord(
            group(
                task_block_a.s(request_id),
                task_block_b.s(request_id),
                task_block_c.s(request_id),
            ),
            final_chain,
        )
        workflow.delay()
        return {'status': 'started', 'request_id': request_id}
    except Exception as exc:
        logger.exception(f"Orchestrator failed for request {request_id}")
        try:
            req = _get_request(request_id)
            req.status = 'failed'
            req.warning_flag = True
            req.warning_message = str(exc)
            req.save(update_fields=['status', 'warning_flag', 'warning_message'])
        except Exception:
            pass
        raise self.retry(exc=exc)



# ══════════════════════════════════════════════════════════════
# BLOCK A — Market Analysis
# ══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def task_block_a(self, request_id: int):
    from apps.market_analysis.models import BlockAResult
    from services.ai_dispatcher import AIDispatcher
    from services.mcc_data_service import MCCDataService

    req = _get_request(request_id)
    mcc_svc = MCCDataService()
    gemini = AIDispatcher()

    population = mcc_svc.get_population(req.district)
    competitors = mcc_svc.get_competitors_from_osm(
        req.latitude, req.longitude, req.mcc_code, radius_m=1000
    )
    competitor_count = len(competitors)

    result = gemini.analyze_market(
        business_type=req.business_type,
        mcc_code=req.mcc_code,
        district=req.district,
        population=population,
        competitor_count=competitor_count,
        request_obj=req,
    )

    is_mock = bool(result.get('is_mock', not bool(gemini.model)))

    # Comparison: user revenue assumption vs AI-derived SOM monthly equivalent
    user_monthly_rev = float(getattr(req, 'target_monthly_revenue', 0) or 0)
    som_monthly = int(result.get('som_uzs', 4_000_000_000)) / 12
    comparison = [_compare(user_monthly_rev, som_monthly,
                           "Maqsadli oylik daromad vs AI SOM/12")]

    block_a, _ = BlockAResult.objects.update_or_create(
        request=req,
        defaults={
            'tam_uzs': int(result.get('tam_uzs', 50_000_000_000)),
            'sam_uzs': int(result.get('sam_uzs', 17_500_000_000)),
            'som_uzs': int(result.get('som_uzs', 4_000_000_000)),
            'saturation_index': float(result.get('saturation_index', 0.5)),
            'gap_score': float(result.get('gap_score', 50.0)),
            'niche_opportunity_score': float(result.get('niche_opportunity_score', 50.0)),
            'ai_commentary': result.get('commentary', ''),
            'raw_data': {**result, 'comparison': comparison},
            'is_mock': is_mock,
        }
    )

    # Validation
    validation = _validate_block_a(block_a)
    _save_validation(block_a, validation)
    if validation['error_count']:
        logger.warning(f"Block A validation errors for request {request_id}: "
                       f"{[i['code'] for i in validation['issues'] if i['level']=='error']}")

    _mark_block_done(req, 'A', 15)
    logger.info(f"Block A done for request {request_id}")
    return request_id


# ══════════════════════════════════════════════════════════════
# BLOCK B — Demand Forecast (Prophet-style simulation)
# ══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def task_block_b(self, request_id: int):
    from apps.demand_forecast.models import BlockBResult
    from services.mcc_data_service import MCCDataService
    from services.ai_dispatcher import AIDispatcher

    req = _get_request(request_id)
    mcc_svc = MCCDataService()
    gemini = AIDispatcher()

    # Use real demand inputs if available, else fall back to MCC history
    daily_customers = getattr(req, 'expected_daily_customers', 0) or 0
    avg_check = float(getattr(req, 'average_check_uzs', 0) or 0)
    working_days = getattr(req, 'working_days_per_week', 7) or 7
    history = []

    if daily_customers > 0 and avg_check > 0:
        # Real input: monthly = daily_customers * avg_check * working_days * 4.3
        monthly_base = daily_customers * avg_check * working_days * 4.3
        revenues = [monthly_base * (0.85 + 0.03 * i) for i in range(24)]
    else:
        history = mcc_svc.get_transaction_history(req.mcc_code, req.district, months=24)
        revenues = [h['total_revenue_uzs'] for h in history]

    # Fit simple linear trend + seasonality (synthetic baseline)
    forecast_12, low_12, high_12 = _generate_forecast(revenues, months=12, mcc_code=req.mcc_code)
    forecast_36, _, _ = _generate_forecast(revenues, months=36, mcc_code=req.mcc_code)

    p10 = int(np.percentile(forecast_12, 10))
    p50 = int(np.percentile(forecast_12, 50))
    p90 = int(np.percentile(forecast_12, 90))

    # Synthetic demand score: how good is p50 relative to investment (target: recover in 36mo)
    monthly_target = float(req.investment_amount) / 36
    synthetic_demand_score = min(100.0, max(0.0, (p50 / monthly_target) * 40)) if monthly_target > 0 else 50.0

    # Seasonality
    ramazon_boost = mcc_svc._monthly_seasonal_factor(3, req.mcc_code) * 100 - 100
    navro_boost = mcc_svc._monthly_seasonal_factor(3, req.mcc_code) * 100 - 100
    weekly = [0.65, 0.85, 0.90, 0.95, 1.10, 1.30, 1.25]  # Mon-Sun

    # ── Gemini review of the synthetic forecast ──
    ai_result = gemini.analyze_demand(
        forecast_12=forecast_12,
        p10=p10, p50=p50, p90=p90,
        synthetic_demand_score=synthetic_demand_score,
        seasonality_weekly=weekly,
        ramazon_boost_pct=ramazon_boost,
        navro_boost_pct=navro_boost,
        request_obj=req,
    )

    # Use Gemini-refined demand score when available, else synthetic
    final_demand_score = float(ai_result.get('demand_score', synthetic_demand_score))
    commentary = ai_result.get('commentary', '')
    is_mock = bool(ai_result.get('is_mock', not bool(gemini.model)))

    # Comparison: user revenue assumption vs AI forecast P50
    user_monthly_rev = float(getattr(req, 'target_monthly_revenue', 0) or 0)
    comparison = [_compare(user_monthly_rev, p50, "Maqsadli oylik daromad vs AI P50")]

    block_b, _ = BlockBResult.objects.update_or_create(
        request=req,
        defaults={
            'monthly_forecast_12': [int(v) for v in forecast_12],
            'monthly_forecast_36': [int(v) for v in forecast_36],
            'confidence_low_12': [int(v) for v in low_12],
            'confidence_high_12': [int(v) for v in high_12],
            'revenue_p10': p10,
            'revenue_p50': p50,
            'revenue_p90': p90,
            'seasonality_ramazon_boost_pct': round(ramazon_boost, 1),
            'seasonality_navro_boost_pct': round(navro_boost, 1),
            'seasonality_weekly': weekly,
            'demand_score': round(final_demand_score, 1),
            'ai_commentary': commentary,
            'raw_data': {
                'history_months': len(history),
                'base_revenue': revenues[-1] if revenues else 0,
                'synthetic_demand_score': round(synthetic_demand_score, 1),
                'ai_review': ai_result,
                'comparison': comparison,
            },
            'is_mock': is_mock,
        }
    )

    # Validation
    validation = _validate_block_b(block_b)
    _save_validation(block_b, validation)
    if validation['error_count']:
        logger.warning(f"Block B validation errors for request {request_id}: "
                       f"{[i['code'] for i in validation['issues'] if i['level']=='error']}")

    _mark_block_done(req, 'B', 15)
    logger.info(f"Block B done for request {request_id} (mock={is_mock})")
    return request_id


def _generate_forecast(history: list, months: int, mcc_code: str):
    """Simple exponential smoothing + trend + seasonal decomposition."""
    from services.mcc_data_service import MCCDataService
    mcc_svc = MCCDataService()

    if not history:
        base = 30_000_000
        history = [base] * 12

    arr = np.array(history, dtype=float)
    # Trend: linear regression
    x = np.arange(len(arr))
    coeffs = np.polyfit(x, arr, 1)
    slope, intercept = coeffs

    forecast = []
    low = []
    high = []
    std = float(np.std(arr)) * 0.5

    for i in range(months):
        t = len(arr) + i
        # Month number (1-12 cycling)
        future_month = ((t) % 12) + 1
        seasonal = mcc_svc._monthly_seasonal_factor(future_month, mcc_code)
        base_val = (slope * t + intercept) * seasonal
        noise_std = std * seasonal
        forecast.append(max(0, base_val))
        low.append(max(0, base_val - 1.5 * noise_std))
        high.append(max(0, base_val + 1.5 * noise_std))

    return forecast, low, high


def _build_b_commentary(business_type, district, p50, demand_score):
    level = "yuqori" if demand_score > 65 else ("o'rtacha" if demand_score > 40 else "past")
    return (
        f"{district} tumanida {business_type} uchun oylik daromad prognozi "
        f"{p50:,} so'mni tashkil etadi (mediana qiymat). "
        f"Talab darajasi {level} bo'lib, mavsumiy ko'rsatkichlar (Navro'z va Ramazon davrlari) "
        f"daromadga sezilarli ijobiy ta'sir ko'rsatadi. "
        f"Hafta oxiri kunlari ish kunlariga nisbatan 30-40% yuqori savdo kuzatiladi. "
        f"[DEMO MA'LUMOT — sintetik prognoz]"
    )


# ══════════════════════════════════════════════════════════════
# BLOCK C — Location Intelligence
# ══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def task_block_c(self, request_id: int):
    from apps.location_intel.models import BlockCResult
    from services.ai_dispatcher import AIDispatcher
    from services.mcc_data_service import MCCDataService
    from services.huggingface_service import HuggingFaceService

    req = _get_request(request_id)

    NON_LOCATION_TYPES = ('textile', 'construction')
    if getattr(req, 'business_category_type', '') in NON_LOCATION_TYPES:
        BlockCResult.objects.update_or_create(
            request=req,
            defaults={
                'location_score': 0,
                'is_mock': True,
                'raw_data': {'skipped': True, 'reason': 'non_location_business'},
                'ai_commentary': (
                    "Bu biznes turi uchun joylashuv tahlili o'tkazilmaydi. "
                    "Tekstil ishlab chiqarish va qurilish korxonalari uchun "
                    "passajirlik oqimi va yaqin atrofdagi raqobatchilar tahlili "
                    "amaliy ahamiyatga ega emas."
                ),
            }
        )
        _mark_block_done(req, 'C', 55)
        logger.info(f"Block C skipped (non-location business) for request {request_id}")
        return request_id

    mcc_svc = MCCDataService()
    gemini = AIDispatcher()
    hf = HuggingFaceService()

    all_comps = mcc_svc.get_competitors_from_osm(
        req.latitude, req.longitude, req.mcc_code, radius_m=1000
    )

    # ── HuggingFace zero-shot classification of the closest competitors ──
    # Adds an `inferred_mcc` field so Blocks C/E can reason about competitor
    # category mix instead of trusting the OSM amenity tag alone.
    for comp in all_comps[:8]:
        try:
            comp['inferred_mcc'] = hf.classify_amenity(
                amenity_name=comp.get('name', ''),
                amenity_type=comp.get('type', ''),
            )
        except Exception as e:
            logger.warning(f"HF classify_amenity failed for '{comp.get('name')}': {e}")
            comp['inferred_mcc'] = comp.get('type', '')

    comps_300m = [c for c in all_comps if c['distance_m'] <= 300]
    comps_1km = [c for c in all_comps if c['distance_m'] <= 1000]

    # Detect anchor businesses (non-competing attractors)
    anchors = _find_anchors(req.latitude, req.longitude)

    result = gemini.evaluate_location(
        lat=req.latitude, lng=req.longitude,
        district=req.district,
        competitors_300m=comps_300m,
        competitors_1km=comps_1km,
        anchors=anchors,
        request_obj=req,
    )

    # Synthetic footfall curves
    hourly = _hourly_footfall_curve(req.mcc_code)
    daily = [0.65, 0.85, 0.90, 0.95, 1.10, 1.35, 1.20]

    is_mock = bool(result.get('is_mock', not bool(gemini.model)))

    # Comparison: user stated foot_traffic vs AI isochrone demand
    user_ft_map = {'very_high': 15000, 'high': 8000, 'medium': 4000, 'low': 1500}
    user_iso10 = user_ft_map.get(getattr(req, 'foot_traffic', 'medium'), 4000)
    ai_iso10   = int(result.get('isochrone_demand_10min', 12000))
    comparison = [_compare(user_iso10, ai_iso10,
                           "Foydalanuvchi trafik bahosi vs AI 10-daqiqa izoхrona")]

    block_c, _ = BlockCResult.objects.update_or_create(
        request=req,
        defaults={
            'location_score': float(result.get('location_score', 60.0)),
            'hourly_footfall': hourly,
            'daily_footfall': daily,
            'isochrone_demand_5min': int(result.get('isochrone_demand_5min', 3500)),
            'isochrone_demand_10min': ai_iso10,
            'anchor_businesses': anchors[:3],
            'anchor_effect_score': float(result.get('anchor_effect_score', 45.0)),
            'competitors_300m': comps_300m,
            'competitors_1km': comps_1km,
            'ai_commentary': result.get('commentary', ''),
            'raw_data': {**result, 'comparison': comparison},
            'is_mock': is_mock,
        }
    )

    # Validation
    validation = _validate_block_c(block_c)
    _save_validation(block_c, validation)
    if validation['error_count']:
        logger.warning(f"Block C validation errors for request {request_id}: "
                       f"{[i['code'] for i in validation['issues'] if i['level']=='error']}")

    _mark_block_done(req, 'C', 15)
    logger.info(f"Block C done for request {request_id}")
    return request_id


def _find_anchors(lat, lng):
    """Query OSM for major attractor buildings near the location."""
    import requests as req_lib
    try:
        query = f"""
[out:json][timeout:10];
(
  node["amenity"~"school|hospital|mall|market|mosque|bank"](around:500,{lat},{lng});
);
out 5;
"""
        resp = req_lib.post(
            "https://overpass-api.de/api/interpreter",
            data={'data': query}, timeout=15
        )
        if resp.status_code == 200:
            elements = resp.json().get('elements', [])
            return [
                {
                    'name': el.get('tags', {}).get('name', 'Ob\'ekt'),
                    'type': el.get('tags', {}).get('amenity', 'building'),
                    'distance_m': 200,
                }
                for el in elements[:5]
            ]
    except Exception:
        pass
    return [
        {'name': 'Mahalliy bozor', 'type': 'market', 'distance_m': 180},
        {'name': 'Maktab', 'type': 'school', 'distance_m': 320},
    ]


def _hourly_footfall_curve(mcc_code: str) -> list:
    """Returns 24-hour footfall multipliers based on business type."""
    if mcc_code in ('5812',):  # Cafe/restaurant
        return [0.1, 0.05, 0.05, 0.05, 0.1, 0.2, 0.5, 0.8, 1.0, 0.9,
                0.8, 1.2, 1.5, 1.2, 0.9, 0.8, 0.9, 1.0, 1.2, 1.3, 1.1, 0.8, 0.5, 0.2]
    elif mcc_code in ('5411',):  # Grocery
        return [0.1, 0.05, 0.05, 0.05, 0.1, 0.3, 0.6, 0.9, 1.1, 1.0,
                0.9, 1.0, 0.9, 0.8, 0.8, 0.9, 1.1, 1.3, 1.2, 1.0, 0.8, 0.6, 0.3, 0.15]
    else:
        return [0.1, 0.05, 0.05, 0.05, 0.1, 0.2, 0.4, 0.7, 1.0, 1.1,
                1.0, 1.0, 0.9, 0.9, 0.9, 1.0, 1.1, 1.2, 1.1, 0.9, 0.7, 0.5, 0.3, 0.15]


# ══════════════════════════════════════════════════════════════
# BLOCK D — Financial Viability (Monte Carlo)
# ══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def task_block_d(self, prev_results, request_id: int):
    from apps.financial_viability.models import BlockDResult
    from apps.demand_forecast.models import BlockBResult
    from services.ai_dispatcher import AIDispatcher

    req = _get_request(request_id)
    gemini = AIDispatcher()

    # Get Block B forecast data
    try:
        block_b = BlockBResult.objects.get(request=req)
        monthly_revenue_p50 = block_b.revenue_p50
    except BlockBResult.DoesNotExist:
        monthly_revenue_p50 = float(req.investment_amount) / 24

    investment = float(req.investment_amount)

    # Compute fixed costs from granular fields (new model); fall back to aggregate
    granular_fixed = (
        float(getattr(req, 'monthly_rent_uzs', 0) or 0) +
        float(getattr(req, 'monthly_salary_budget', 0) or 0) +
        float(getattr(req, 'monthly_utilities', 0) or 0)
    )
    fixed_costs = granular_fixed if granular_fixed > 0 else (
        float(req.monthly_fixed_costs) if req.monthly_fixed_costs else monthly_revenue_p50 * 0.20
    )

    # Use cogs_percentage for variable cost (new field), fallback to variable_cost_pct
    cogs_pct = float(getattr(req, 'cogs_percentage', 0) or req.variable_cost_pct or 35.0)
    variable_pct = cogs_pct / 100
    markup_pct = req.planned_markup_pct / 100

    # ── Monte Carlo (10,000 simulations) ──
    np.random.seed(42)
    N = 10000
    rev_samples = np.random.normal(monthly_revenue_p50, monthly_revenue_p50 * 0.20, N)
    var_cost_samples = rev_samples * np.random.normal(variable_pct, 0.05, N)
    fixed_samples = np.full(N, fixed_costs) * np.random.normal(1.0, 0.05, N)

    gross_profit = rev_samples * markup_pct
    monthly_profit_samples = gross_profit - var_cost_samples - fixed_samples

    # Distribution (use 1000 sample points for storage)
    distribution_sample = monthly_profit_samples[::10].tolist()
    mc_mean = float(np.mean(monthly_profit_samples))
    mc_std = float(np.std(monthly_profit_samples))
    mc_success_prob = float(np.mean(monthly_profit_samples > 0) * 100)

    # Break-even
    avg_monthly_profit = np.mean(monthly_profit_samples)
    if avg_monthly_profit > 0:
        bep_months = investment / avg_monthly_profit
    else:
        bep_months = 999.0
    bep_revenue = fixed_costs / (markup_pct - variable_pct) if (markup_pct - variable_pct) > 0 else 0

    # ROI
    annual_profit = avg_monthly_profit * 12
    roi_12 = (annual_profit / investment * 100) if investment > 0 else 0
    roi_36 = (annual_profit * 3 / investment * 100) if investment > 0 else 0

    # Unit economics
    cac = int(monthly_revenue_p50 * 0.05)
    ltv = int(avg_monthly_profit * 18) if avg_monthly_profit > 0 else 0
    ltv_cac = (ltv / cac) if cac > 0 else 0
    gross_margin = markup_pct * 100

    # Cash flow 24 months
    cumulative = -investment
    cash_flow = []
    for i in range(24):
        seasonal = 1.0 + 0.1 * np.sin(i * np.pi / 6)
        cumulative += avg_monthly_profit * seasonal
        cash_flow.append(int(cumulative))

    # Synthetic viability score (baseline)
    synthetic_viability_score = _compute_viability_score(
        bep_months, roi_12, mc_success_prob, ltv_cac
    )

    # ── Gemini review of the Monte Carlo output ──
    ai_result = gemini.analyze_financial_viability(
        investment_uzs=investment,
        monthly_revenue_p50=int(monthly_revenue_p50),
        fixed_costs_uzs=fixed_costs,
        cogs_pct=cogs_pct,
        bep_months=min(bep_months, 999.0),
        bep_revenue_uzs=int(max(0, bep_revenue)),
        roi_12mo=roi_12,
        roi_36mo=roi_36,
        mc_success_probability=mc_success_prob,
        mc_mean_profit=int(mc_mean),
        mc_std_profit=int(mc_std),
        cac_uzs=cac,
        ltv_uzs=ltv,
        ltv_cac_ratio=ltv_cac,
        gross_margin_pct=gross_margin,
        cash_flow_24mo=cash_flow,
        synthetic_viability_score=synthetic_viability_score,
        request_obj=req,
    )

    final_viability_score = float(ai_result.get('viability_score', synthetic_viability_score))
    commentary = ai_result.get('commentary', '')
    is_mock = bool(ai_result.get('is_mock', not bool(gemini.model)))

    # Comparison: user target revenue vs AI revenue P50, user investment vs annual BEP revenue
    user_target = float(getattr(req, 'target_monthly_revenue', 0) or 0)
    bep_annual  = int(max(0, bep_revenue)) * 12
    comparison  = [
        _compare(user_target, monthly_revenue_p50,
                 "Maqsadli oylik daromad vs AI Monte Carlo P50"),
        _compare(investment, bep_annual,
                 "Investitsiya vs yillik tannarx qoplash daromadi"),
    ]

    block_d, _ = BlockDResult.objects.update_or_create(
        request=req,
        defaults={
            'breakeven_months': round(min(bep_months, 999.0), 1),
            'breakeven_revenue_uzs': int(max(0, bep_revenue)),
            'mc_profit_distribution': [int(v) for v in distribution_sample],
            'mc_mean_profit': int(mc_mean),
            'mc_std_profit': int(mc_std),
            'mc_success_probability': round(mc_success_prob, 1),
            'roi_12mo': round(roi_12, 1),
            'roi_36mo': round(roi_36, 1),
            'cac_uzs': cac,
            'ltv_uzs': ltv,
            'ltv_cac_ratio': round(ltv_cac, 2),
            'gross_margin_pct': round(gross_margin, 1),
            'cash_flow_monthly_24': cash_flow,
            'viability_score': round(final_viability_score, 1),
            'ai_commentary': commentary,
            'raw_data': {
                'investment': investment,
                'fixed_costs': fixed_costs,
                'synthetic_viability_score': round(synthetic_viability_score, 1),
                'ai_review': ai_result,
                'comparison': comparison,
            },
            'is_mock': is_mock,
        }
    )

    # Validation
    validation = _validate_block_d(block_d)
    _save_validation(block_d, validation)
    if validation['error_count']:
        logger.warning(f"Block D validation errors for request {request_id}: "
                       f"{[i['code'] for i in validation['issues'] if i['level']=='error']}")

    _mark_block_done(req, 'D', 15)
    logger.info(f"Block D done for request {request_id} (mock={is_mock})")
    return request_id


def _compute_viability_score(bep_months, roi_12, mc_success_prob, ltv_cac):
    score = 0.0
    # BEP score (best < 12 months, worst > 48)
    if bep_months < 12:
        score += 35
    elif bep_months < 24:
        score += 25
    elif bep_months < 36:
        score += 15
    elif bep_months < 48:
        score += 5
    # ROI score
    if roi_12 > 30:
        score += 30
    elif roi_12 > 15:
        score += 20
    elif roi_12 > 5:
        score += 10
    # MC success prob
    score += mc_success_prob * 0.20
    # LTV/CAC
    if ltv_cac > 5:
        score += 15
    elif ltv_cac > 3:
        score += 10
    elif ltv_cac > 1:
        score += 5
    return min(100.0, score)


# ══════════════════════════════════════════════════════════════
# BLOCK E — Competition & Risk
# ══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def task_block_e(self, prev_result, request_id: int):
    from apps.competition_risk.models import BlockEResult
    from apps.location_intel.models import BlockCResult
    from services.ai_dispatcher import AIDispatcher
    from services.mcc_data_service import MCCDataService

    req = _get_request(request_id)
    gemini = AIDispatcher()
    mcc_svc = MCCDataService()

    churn_rate = mcc_svc.get_district_churn_rate(req.district, req.mcc_code)

    # Reuse competitor data from Block C if available
    try:
        block_c = BlockCResult.objects.get(request=req)
        all_competitors = block_c.competitors_1km
        comps_300m = block_c.competitors_300m
    except BlockCResult.DoesNotExist:
        all_competitors = mcc_svc.get_competitors_from_osm(
            req.latitude, req.longitude, req.mcc_code, 1000
        )
        comps_300m = [c for c in all_competitors if c['distance_m'] <= 300]

    result = gemini.analyze_competition(
        competitors=all_competitors,
        business_type=req.business_type,
        district=req.district,
        district_churn_rate=churn_rate,
        request_obj=req,
    )

    # Apply closure probabilities back to competitor dicts
    closure_probs = result.get('closure_probabilities', {})
    for comp in all_competitors:
        comp['closure_probability'] = closure_probs.get(comp['name'], round(churn_rate / 100, 2))

    market_risk = float(result.get('market_risk_score', 50.0))
    market_risk_inv = round(100.0 - market_risk, 1)

    is_mock = bool(result.get('is_mock', not bool(gemini.model)))

    # Comparison: user-stated nearby competitor count vs OSM-sourced 300m count
    n_300_ai = len(comps_300m)
    _known_raw = getattr(req, 'known_competitors', '') or ''
    try:
        n_300_user = int(_known_raw)
    except (ValueError, TypeError):
        # TextField: count non-empty lines as competitor entries
        n_300_user = len([l for l in _known_raw.splitlines() if l.strip()])
    comparison = [_compare(n_300_user, n_300_ai,
                           "Foydalanuvchi raqobatchilar soni vs AI OSM 300m")]

    block_e, _ = BlockEResult.objects.update_or_create(
        request=req,
        defaults={
            'competitors_300m': comps_300m,
            'competitors_1km': all_competitors,
            'entry_barriers': result.get('entry_barriers', []),
            'market_risk_score': market_risk,
            'market_risk_score_inv': market_risk_inv,
            'district_churn_rate': churn_rate,
            'recommendation_notes': result.get('recommendation_notes', ''),
            'ai_commentary': result.get('commentary', ''),
            'raw_data': {**result, 'comparison': comparison},
            'is_mock': is_mock,
        }
    )

    # Validation
    validation = _validate_block_e(block_e)
    _save_validation(block_e, validation)
    if validation['error_count']:
        logger.warning(f"Block E validation errors for request {request_id}: "
                       f"{[i['code'] for i in validation['issues'] if i['level']=='error']}")

    _mark_block_done(req, 'E', 15)
    logger.info(f"Block E done for request {request_id}")
    return request_id


# ══════════════════════════════════════════════════════════════
# FINAL DECISION
# ══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def task_final_decision(self, prev_result, request_id: int):
    from services.ai_dispatcher import AIDispatcher
    from services.scoring_engine import ScoringEngine
    from apps.market_analysis.models import BlockAResult
    from apps.demand_forecast.models import BlockBResult
    from apps.location_intel.models import BlockCResult
    from apps.financial_viability.models import BlockDResult
    from apps.competition_risk.models import BlockEResult

    req = _get_request(request_id)
    engine = ScoringEngine()
    gemini = AIDispatcher()

    # Gather block results
    block_a = BlockAResult.objects.filter(request=req).first()
    block_b = BlockBResult.objects.filter(request=req).first()
    block_c = BlockCResult.objects.filter(request=req).first()
    block_d = BlockDResult.objects.filter(request=req).first()
    block_e = BlockEResult.objects.filter(request=req).first()

    block_scores = ScoringEngine.derive_block_scores(block_a, block_b, block_c, block_d, block_e)
    scoring_result = engine.compute_composite(block_scores)
    composite_score = scoring_result['composite_score']

    # Gemini final commentary
    final = gemini.final_decision(
        request_data={
            'business_type': req.business_type,
            'district': req.district,
            'investment_amount': float(req.investment_amount),
        },
        block_scores=block_scores,
        composite_score=composite_score,
    )

    rec_map = {'HA': 'YES', "YO'Q": 'NO', 'EHTIYOT': 'CAUTION'}
    raw_rec = final.get('recommendation', scoring_result['recommendation'])
    recommendation = rec_map.get(raw_rec, raw_rec)
    if recommendation not in ('YES', 'NO', 'CAUTION'):
        recommendation = scoring_result['recommendation']

    # ── Validation-based recommendation capping ──
    all_val = _collect_all_validations(block_a, block_b, block_c, block_d, block_e)
    error_count = len(all_val['errors'])
    warning_flag = False
    warning_message = ''

    if error_count >= 3:
        # Critical: too many hard failures across blocks → force NO
        if recommendation != 'NO':
            logger.warning(f"Capping recommendation from {recommendation} to NO "
                           f"({error_count} block errors) for request {request_id}")
            recommendation = 'NO'
        warning_flag = True
        warning_message = (
            f"Tahlil natijalari {error_count} ta jiddiy muammoni aniqladi. "
            f"Kredit tavsiyasi avtomatik ravishda 'NO'ga o'zgartirildi.\n"
            + "\n".join(f"• {e}" for e in all_val['errors'][:5])
        )
    elif error_count >= 1 and recommendation == 'YES':
        # At least one hard error but score would say YES → downgrade to CAUTION
        logger.warning(f"Downgrading recommendation from YES to CAUTION "
                       f"({error_count} block errors) for request {request_id}")
        recommendation = 'CAUTION'
        warning_flag = True
        warning_message = (
            f"Tahlil {error_count} ta jiddiy muammoni aniqladi. "
            f"Kredit tavsiyasi 'EHTIYOT'ga o'zgartirildi.\n"
            + "\n".join(f"• {e}" for e in all_val['errors'])
        )
        if all_val['warnings']:
            warning_message += "\nOgohlantirishlar:\n" + "\n".join(
                f"• {w}" for w in all_val['warnings'][:3]
            )
    elif all_val['warnings']:
        warning_flag = True
        warning_message = "Ogohlantirishlar:\n" + "\n".join(
            f"• {w}" for w in all_val['warnings'][:5]
        )

    req.final_score = composite_score
    req.final_recommendation = recommendation
    req.final_commentary = final.get('commentary', '')
    req.credit_tier = final.get('credit_tier', scoring_result['credit_tier'])
    req.warning_flag = warning_flag
    req.warning_message = warning_message
    req.status = 'done'
    req.progress_pct = 100

    # External source-backed checks for transparent result pages.
    try:
        from services.web_evidence_service import ExternalEvidenceService

        report = ExternalEvidenceService().build_report(req)
        req.external_checks = report
        req.external_checks_updated_at = timezone.now()
    except Exception as exc:
        logger.warning("External evidence build failed for request %s: %s", request_id, exc)
        req.external_checks = {}
        req.external_checks_updated_at = None

    req.save(update_fields=[
        'final_score', 'final_recommendation', 'final_commentary',
        'credit_tier', 'warning_flag', 'warning_message',
        'status', 'progress_pct',
        'external_checks', 'external_checks_updated_at'
    ])

    logger.info(f"Final decision done for request {request_id}: {recommendation} ({composite_score:.1f})")
    return {'recommendation': recommendation, 'score': composite_score}


# ══════════════════════════════════════════════════════════════
# CATEGORY-SPECIFIC TASKS
# ══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def task_category_hotel(self, request_id: int):
    from apps.category_analysis.models import HotelAnalysisResult
    from services.ai_dispatcher import AIDispatcher

    req = _get_request(request_id)
    gemini = AIDispatcher()
    result = gemini.analyze_hotel(req)

    HotelAnalysisResult.objects.update_or_create(
        request=req,
        defaults={
            'location_score':           result.get('location_score', 50.0),
            'tourist_flow_monthly':     result.get('tourist_flow_monthly', []),
            'occupancy_forecast':       result.get('occupancy_forecast', []),
            'revpar_forecast':          result.get('revpar_forecast', []),
            'monthly_revenue_forecast': result.get('monthly_revenue_forecast', []),
            'revenue_p50_usd':          result.get('revenue_p50_usd', 0.0),
            'seasonality_notes':        result.get('seasonality_notes', ''),
            'risk_flags':               result.get('risk_flags', []),
            'subsidy_eligible':         result.get('subsidy_eligible', False),
            'credit_structure_recommendation': result.get('credit_structure_recommendation', ''),
            'ai_commentary':            result.get('ai_commentary', ''),
            'raw_data':                 result,
            'is_mock':                  result.get('is_mock', True),
        }
    )
    _mark_block_done(req, 'HOTEL', 0)
    logger.info(f"Category Hotel task done for request {request_id}")
    return request_id


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def task_category_construction(self, request_id: int):
    from apps.category_analysis.models import ConstructionAnalysisResult
    from services.ai_dispatcher import AIDispatcher

    req = _get_request(request_id)
    gemini = AIDispatcher()
    result = gemini.analyze_construction(req)

    ConstructionAnalysisResult.objects.update_or_create(
        request=req,
        defaults={
            'cash_flow_timeline':     result.get('cash_flow_timeline', []),
            'cumulative_cash_flow':   result.get('cumulative_cash_flow', []),
            'monthly_loan_payment':   result.get('monthly_loan_payment', 0.0),
            'breakeven_month':        result.get('breakeven_month'),
            'faza_1_risk':            result.get('faza_1_risk', 'high'),
            'faza_2_risk':            result.get('faza_2_risk', 'medium'),
            'faza_3_risk':            result.get('faza_3_risk', 'low'),
            'license_risk_flag':      result.get('license_risk_flag', True),
            'contract_pipeline_score':result.get('contract_pipeline_score', 30.0),
            'market_size_uzs':        result.get('market_size_uzs', 0),
            'tender_opportunity_score':result.get('tender_opportunity_score', 0.0),
            'ai_commentary':          result.get('ai_commentary', ''),
            'raw_data':               result,
            'is_mock':                result.get('is_mock', True),
        }
    )
    _mark_block_done(req, 'CONSTRUCTION', 0)
    logger.info(f"Category Construction task done for request {request_id}")
    return request_id


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def task_category_textile(self, request_id: int):
    from apps.category_analysis.models import TextileAnalysisResult
    from services.ai_dispatcher import AIDispatcher

    req = _get_request(request_id)
    gemini = AIDispatcher()
    result = gemini.analyze_textile(req)

    TextileAnalysisResult.objects.update_or_create(
        request=req,
        defaults={
            'market_research_data':     result.get('market_research_data', {}),
            'export_readiness_score':   result.get('export_readiness_score', 0.0),
            'certification_score':      result.get('certification_score', 0.0),
            'buyer_network_score':      result.get('buyer_network_score', 0.0),
            'market_access_score':      result.get('market_access_score', 0.0),
            'certification_risk_flag':  result.get('certification_risk_flag', False),
            'readiness_interpretation': result.get('readiness_interpretation', ''),
            'export_contract_bonus':    result.get('export_contract_bonus', False),
            'free_zone_eligible':       result.get('free_zone_eligible', False),
            'ai_commentary':            result.get('ai_commentary', ''),
            'raw_data':                 result,
            'is_mock':                  result.get('is_mock', True),
        }
    )
    _mark_block_done(req, 'TEXTILE', 0)
    logger.info(f"Category Textile task done for request {request_id}")
    return request_id


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def task_category_trade(self, request_id: int):
    from apps.category_analysis.models import TradeAnalysisResult
    from services.ai_dispatcher import AIDispatcher

    req = _get_request(request_id)
    gemini = AIDispatcher()
    result = gemini.analyze_trade(req)

    TradeAnalysisResult.objects.update_or_create(
        request=req,
        defaults={
            'working_capital_needed':      result.get('working_capital_needed', 0),
            'supplier_float':              result.get('supplier_float', 0),
            'net_working_capital_gap':     result.get('net_working_capital_gap', 0),
            'monthly_revenue_estimate':    result.get('monthly_revenue_estimate', 0),
            'gross_profit_monthly':        result.get('gross_profit_monthly', 0),
            'location_foot_traffic_score': result.get('location_foot_traffic_score', 0.0),
            'competitor_density_score':    result.get('competitor_density_score', 0.0),
            'overall_location_score':      result.get('overall_location_score', 0.0),
            'recommended_loan_type':       result.get('recommended_loan_type', ''),
            'recommended_term_months':     result.get('recommended_term_months', 24),
            'ai_commentary':               result.get('ai_commentary', ''),
            'raw_data':                    result,
            'is_mock':                     result.get('is_mock', True),
        }
    )
    _mark_block_done(req, 'TRADE', 0)
    logger.info(f"Category Trade task done for request {request_id}")
    return request_id
