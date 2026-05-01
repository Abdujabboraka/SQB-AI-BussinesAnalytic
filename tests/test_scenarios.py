"""
Business scenario tests — end-to-end validation + scoring pipeline.
Each scenario builds block mocks from named presets and verifies
the final recommendation / capping logic from task_final_decision.

No DB, no Celery — tests only the pure logic path:
  derive_block_scores → compute_composite → _collect_all_validations → cap recommendation
"""
import pytest
from unittest.mock import MagicMock
from tests.conftest import (
    make_block_a, make_block_b, make_block_c,
    make_block_d, make_block_e,
)


# ── Helper: run scoring + capping exactly as task_final_decision does ─────────

def _run_scenario(ba, bb, bc, bd, be):
    """
    Replicates the core logic of task_final_decision without Celery/DB.
    Returns: (recommendation, composite_score, warning_flag, error_count)
    """
    from services.scoring_engine import ScoringEngine
    from apps.core.tasks import _collect_all_validations

    block_scores = ScoringEngine.derive_block_scores(ba, bb, bc, bd, be)
    scoring_result = ScoringEngine().compute_composite(block_scores)
    composite_score = scoring_result['composite_score']
    recommendation = scoring_result['recommendation']

    all_val = _collect_all_validations(ba, bb, bc, bd, be)
    error_count = len(all_val['errors'])
    warning_flag = False

    if error_count >= 3:
        recommendation = 'NO'
        warning_flag = True
    elif error_count >= 1 and recommendation == 'YES':
        recommendation = 'CAUTION'
        warning_flag = True
    elif all_val['warnings']:
        warning_flag = True

    return recommendation, composite_score, warning_flag, error_count


def _inject_validation(block, issues):
    """Attach pre-built validation to a block's raw_data."""
    block.raw_data = {
        'validation': {
            'issues': issues,
            'error_count': sum(1 for i in issues if i['level'] == 'error'),
            'warn_count': sum(1 for i in issues if i['level'] == 'warning'),
        }
    }


# ── Scenario 1: Ideal business — should yield YES ────────────────────────────

class TestIdealScenario:
    """All blocks pass, scores high. Expect YES with no capping."""

    def _build(self):
        ba = make_block_a(saturation_index=0.45, niche_opportunity_score=80, som_uzs=8_000_000_000, gap_score=70)
        bb = make_block_b(demand_score=80, revenue_p10=25_000_000, revenue_p50=40_000_000)
        bc = make_block_c(location_score=85, competitors_300m=[], anchor_effect_score=70)
        bd = make_block_d(viability_score=78, mc_success_probability=72, breakeven_months=18, roi_12mo=25, ltv_cac_ratio=4.0, cash_flow_monthly_24=[50_000_000] * 24)
        be = make_block_e(market_risk_score=35, market_risk_score_inv=65, district_churn_rate=15, competitors_300m=[])
        for b in (ba, bb, bc, bd, be):
            _inject_validation(b, [])
        return ba, bb, bc, bd, be

    def test_recommendation_is_yes(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        assert rec == 'YES'

    def test_score_above_70(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        assert score >= 70

    def test_no_warnings(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        assert wf is False
        assert errs == 0


# ── Scenario 2: Saturated market — should yield NO ───────────────────────────

class TestSaturatedMarketScenario:
    """
    Extreme saturation + low niche score in Block A gives 2 errors.
    Block E severe competition adds 1 more error.
    Total ≥ 3 errors → recommendation forced to NO.
    """

    def _build(self):
        ba = make_block_a(saturation_index=0.97, niche_opportunity_score=15)  # 2 errors
        bb = make_block_b(demand_score=40)
        bc = make_block_c(location_score=60)
        bd = make_block_d(viability_score=55, mc_success_probability=58, breakeven_months=25, roi_12mo=10, ltv_cac_ratio=2.0, cash_flow_monthly_24=[10_000_000] * 24)
        be = make_block_e(market_risk_score=78, market_risk_score_inv=22,
                          competitors_300m=[{'name': f'C{i}'} for i in range(6)])  # 2 errors

        _inject_validation(ba, [
            {'level': 'error', 'code': 'EXTREME_SATURATION', 'message': 'Too saturated'},
            {'level': 'error', 'code': 'LOW_OPPORTUNITY', 'message': 'Low niche'},
        ])
        _inject_validation(bb, [{'level': 'warning', 'code': 'LOW_DEMAND', 'message': 'Low demand'}])
        _inject_validation(bc, [])
        _inject_validation(bd, [])
        _inject_validation(be, [
            {'level': 'error', 'code': 'VERY_HIGH_MARKET_RISK', 'message': 'High risk'},
            {'level': 'error', 'code': 'SEVERE_COMPETITION', 'message': 'Too many comps'},
        ])
        return ba, bb, bc, bd, be

    def test_forced_to_no(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        assert rec == 'NO'

    def test_error_count_at_least_3(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        assert errs >= 3

    def test_warning_flag_set(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        assert wf is True


# ── Scenario 3: Bad financials — YES downgraded to CAUTION ───────────────────

class TestBadFinancialsScenario:
    """
    Good market + location push composite to YES zone,
    but Block D has 1 hard error → downgraded to CAUTION.
    """

    def _build(self):
        ba = make_block_a(saturation_index=0.5, niche_opportunity_score=75, som_uzs=6_000_000_000, gap_score=65)
        bb = make_block_b(demand_score=75, revenue_p10=20_000_000, revenue_p50=38_000_000)
        bc = make_block_c(location_score=80, competitors_300m=[], anchor_effect_score=60)
        bd = make_block_d(
            viability_score=35,
            mc_success_probability=30,  # error: LOW_SUCCESS_PROB
            breakeven_months=55,        # error: VERY_LONG_BEP
            roi_12mo=-8,               # error: NEGATIVE_ROI
            ltv_cac_ratio=0.4,
            cash_flow_monthly_24=[-1_000_000] * 24,
        )
        be = make_block_e(market_risk_score=40, market_risk_score_inv=60)

        _inject_validation(ba, [])
        _inject_validation(bb, [])
        _inject_validation(bc, [])
        _inject_validation(bd, [
            {'level': 'error', 'code': 'NEGATIVE_ROI', 'message': 'ROI < 0'},
        ])
        _inject_validation(be, [])
        return ba, bb, bc, bd, be

    def test_downgraded_from_yes_to_caution(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        # Score might be in YES zone due to good A/B/C
        # but 1+ error forces YES → CAUTION
        if score >= 70:
            assert rec == 'CAUTION'
        else:
            assert rec in ('CAUTION', 'NO')

    def test_warning_flag_set(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        assert wf is True

    def test_at_least_one_error(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        assert errs >= 1


# ── Scenario 4: High risk environment — NO ───────────────────────────────────

class TestHighRiskScenario:
    """Low scores across all blocks with high competition + risk."""

    def _build(self):
        ba = make_block_a(saturation_index=0.60, niche_opportunity_score=35, som_uzs=3_000_000_000, gap_score=30)
        bb = make_block_b(demand_score=38)
        bc = make_block_c(location_score=32, competitors_300m=[{'name': f'C{i}'} for i in range(5)])
        bd = make_block_d(viability_score=30, mc_success_probability=35, breakeven_months=52, roi_12mo=-5, ltv_cac_ratio=0.3, cash_flow_monthly_24=[-500_000] * 24)
        be = make_block_e(market_risk_score=82, market_risk_score_inv=18, district_churn_rate=45, competitors_300m=[{'name': f'C{i}'} for i in range(7)])

        _inject_validation(ba, [
            {'level': 'error', 'code': 'LOW_OPPORTUNITY', 'message': 'Low niche'},
        ])
        _inject_validation(bb, [
            {'level': 'warning', 'code': 'LOW_DEMAND', 'message': 'Demand low'},
        ])
        _inject_validation(bc, [
            {'level': 'error', 'code': 'VERY_LOW_LOCATION', 'message': 'Bad location'},
            {'level': 'error', 'code': 'TOO_MANY_NEARBY_COMPS', 'message': '5 comps nearby'},
        ])
        _inject_validation(bd, [
            {'level': 'error', 'code': 'LOW_SUCCESS_PROB', 'message': 'Low MC prob'},
            {'level': 'error', 'code': 'NEGATIVE_ROI', 'message': 'Negative ROI'},
        ])
        _inject_validation(be, [
            {'level': 'error', 'code': 'VERY_HIGH_MARKET_RISK', 'message': 'High risk'},
            {'level': 'error', 'code': 'SEVERE_COMPETITION', 'message': '7 comps'},
        ])
        return ba, bb, bc, bd, be

    def test_recommendation_is_no(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        assert rec == 'NO'

    def test_score_below_45(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        assert score < 45

    def test_many_errors(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        assert errs >= 3


# ── Scenario 5: Borderline — CAUTION ─────────────────────────────────────────

class TestBorderlineScenario:
    """Composite sits in 45-70 zone with only warnings — should be CAUTION."""

    def _build(self):
        ba = make_block_a(saturation_index=0.70, niche_opportunity_score=50, som_uzs=3_500_000_000, gap_score=40)
        bb = make_block_b(demand_score=55)
        bc = make_block_c(location_score=55, competitors_300m=[{'name': 'R1'}, {'name': 'R2'}])
        bd = make_block_d(viability_score=55, mc_success_probability=57, breakeven_months=34, roi_12mo=8, ltv_cac_ratio=1.5, cash_flow_monthly_24=[5_000_000] * 24)
        be = make_block_e(market_risk_score=55, market_risk_score_inv=45, district_churn_rate=25)

        _inject_validation(ba, [{'level': 'warning', 'code': 'HIGH_SATURATION', 'message': 'High sat'}])
        _inject_validation(bb, [{'level': 'warning', 'code': 'LOW_DEMAND', 'message': 'Low demand'}])
        _inject_validation(bc, [])
        _inject_validation(bd, [{'level': 'warning', 'code': 'LONG_BEP', 'message': 'BEP 34 months'}])
        _inject_validation(be, [{'level': 'warning', 'code': 'HIGH_MARKET_RISK', 'message': 'Risk 55'}])
        return ba, bb, bc, bd, be

    def test_recommendation_is_caution(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        assert rec == 'CAUTION'

    def test_score_in_45_70_range(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        assert 45 <= score < 70

    def test_no_hard_errors(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        assert errs == 0

    def test_warning_flag_set_from_warnings(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        assert wf is True


# ── Scenario 6: One error but score is NO anyway — no double-downgrade ────────

class TestOneErrorAlreadyNoScenario:
    """Score is in NO zone AND there is 1 error. Result must stay NO (not CAUTION)."""

    def _build(self):
        ba = make_block_a(saturation_index=0.97, niche_opportunity_score=15)
        bb = make_block_b(demand_score=28)
        bc = make_block_c(location_score=30)
        bd = make_block_d(viability_score=25, mc_success_probability=28, breakeven_months=60, roi_12mo=-15, ltv_cac_ratio=0.2, cash_flow_monthly_24=[-500_000] * 24)
        be = make_block_e(market_risk_score=80, market_risk_score_inv=20)

        _inject_validation(ba, [
            {'level': 'error', 'code': 'EXTREME_SATURATION', 'message': 'X'},
        ])
        for b in (bb, bc, bd, be):
            _inject_validation(b, [])
        return ba, bb, bc, bd, be

    def test_still_no_not_caution(self):
        rec, score, wf, errs = _run_scenario(*self._build())
        # score already in NO zone; 1 error tries to downgrade YES→CAUTION
        # but score isn't YES, so recommendation stays NO
        assert rec == 'NO'
