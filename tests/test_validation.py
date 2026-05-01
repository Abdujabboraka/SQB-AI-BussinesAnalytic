"""
Unit tests for all _validate_block_* functions.
Uses MagicMock objects — no DB required.
"""
import pytest
from tests.conftest import (
    make_block_a, make_block_b, make_block_c,
    make_block_d, make_block_e,
)


def _va(block): from apps.core.tasks import _validate_block_a; return _validate_block_a(block)
def _vb(block): from apps.core.tasks import _validate_block_b; return _validate_block_b(block)
def _vc(block): from apps.core.tasks import _validate_block_c; return _validate_block_c(block)
def _vd(block): from apps.core.tasks import _validate_block_d; return _validate_block_d(block)
def _ve(block): from apps.core.tasks import _validate_block_e; return _validate_block_e(block)


# ── Block A ───────────────────────────────────────────────────────────────────

class TestValidateBlockA:
    def test_healthy_block_has_no_issues(self):
        b = make_block_a(saturation_index=0.55, niche_opportunity_score=65, som_uzs=5_000_000_000, gap_score=50)
        r = _va(b)
        assert r['error_count'] == 0
        assert r['warn_count'] == 0

    def test_extreme_saturation_is_error(self):
        b = make_block_a(saturation_index=0.97)
        r = _va(b)
        codes = [i['code'] for i in r['issues']]
        assert 'EXTREME_SATURATION' in codes
        assert r['error_count'] >= 1

    def test_high_saturation_is_warning_not_error(self):
        b = make_block_a(saturation_index=0.85)
        r = _va(b)
        levels = {i['code']: i['level'] for i in r['issues']}
        assert levels.get('HIGH_SATURATION') == 'warning'
        assert 'EXTREME_SATURATION' not in levels

    def test_saturation_exactly_095_is_error(self):
        b = make_block_a(saturation_index=0.951)
        r = _va(b)
        codes = [i['code'] for i in r['issues']]
        assert 'EXTREME_SATURATION' in codes

    def test_saturation_exactly_080_is_warning(self):
        b = make_block_a(saturation_index=0.81)
        r = _va(b)
        codes = [i['code'] for i in r['issues']]
        assert 'HIGH_SATURATION' in codes

    def test_low_niche_score_is_error(self):
        b = make_block_a(niche_opportunity_score=20)
        r = _va(b)
        codes = [i['code'] for i in r['issues']]
        assert 'LOW_OPPORTUNITY' in codes
        assert r['error_count'] >= 1

    def test_niche_score_exactly_30_no_error(self):
        b = make_block_a(niche_opportunity_score=30)
        r = _va(b)
        codes = [i['code'] for i in r['issues']]
        assert 'LOW_OPPORTUNITY' not in codes

    def test_low_som_is_warning(self):
        b = make_block_a(som_uzs=1_000_000_000)  # 1B < 2B threshold
        r = _va(b)
        codes = [i['code'] for i in r['issues']]
        assert 'LOW_SOM' in codes
        assert all(i['level'] == 'warning' for i in r['issues'] if i['code'] == 'LOW_SOM')

    def test_low_gap_score_is_warning(self):
        b = make_block_a(gap_score=20)
        r = _va(b)
        codes = [i['code'] for i in r['issues']]
        assert 'LOW_GAP_SCORE' in codes

    def test_multiple_issues_counted_correctly(self):
        b = make_block_a(
            saturation_index=0.97,   # error
            niche_opportunity_score=10,  # error
            som_uzs=500_000_000,     # warning
            gap_score=10,            # warning
        )
        r = _va(b)
        assert r['error_count'] == 2
        assert r['warn_count'] == 2

    def test_result_has_required_keys(self):
        r = _va(make_block_a())
        assert 'issues' in r
        assert 'error_count' in r
        assert 'warn_count' in r

    def test_each_issue_has_required_fields(self):
        b = make_block_a(saturation_index=0.97)
        r = _va(b)
        for issue in r['issues']:
            assert 'level' in issue
            assert 'code' in issue
            assert 'message' in issue
            assert issue['level'] in ('error', 'warning')


# ── Block B ───────────────────────────────────────────────────────────────────

class TestValidateBlockB:
    def test_healthy_block_no_issues(self):
        b = make_block_b(demand_score=70, revenue_p10=20_000_000, revenue_p50=30_000_000)
        r = _vb(b)
        assert r['error_count'] == 0
        assert r['warn_count'] == 0

    def test_very_low_demand_is_error(self):
        b = make_block_b(demand_score=25)
        r = _vb(b)
        codes = [i['code'] for i in r['issues']]
        assert 'VERY_LOW_DEMAND' in codes
        assert r['error_count'] >= 1

    def test_low_demand_is_warning(self):
        b = make_block_b(demand_score=40)
        r = _vb(b)
        levels = {i['code']: i['level'] for i in r['issues']}
        assert levels.get('LOW_DEMAND') == 'warning'
        assert 'VERY_LOW_DEMAND' not in levels

    def test_demand_exactly_30_no_error(self):
        b = make_block_b(demand_score=30)
        r = _vb(b)
        codes = [i['code'] for i in r['issues']]
        assert 'VERY_LOW_DEMAND' not in codes

    def test_declining_trend_detected(self):
        # First 3 months high, last 3 months low
        forecast = [50_000_000, 50_000_000, 50_000_000,
                    40_000_000, 35_000_000, 30_000_000,
                    28_000_000, 26_000_000, 24_000_000,
                    20_000_000, 18_000_000, 15_000_000]
        b = make_block_b(demand_score=55, monthly_forecast_12=forecast)
        r = _vb(b)
        codes = [i['code'] for i in r['issues']]
        assert 'DECLINING_TREND' in codes

    def test_stable_trend_no_declining_warning(self):
        forecast = [30_000_000] * 12
        b = make_block_b(demand_score=60, monthly_forecast_12=forecast)
        r = _vb(b)
        codes = [i['code'] for i in r['issues']]
        assert 'DECLINING_TREND' not in codes

    def test_wide_confidence_band_warning(self):
        # p50 / p10 > 4 → warning
        b = make_block_b(revenue_p10=5_000_000, revenue_p50=25_000_000)
        r = _vb(b)
        codes = [i['code'] for i in r['issues']]
        assert 'HIGH_UNCERTAINTY' in codes

    def test_narrow_confidence_band_no_warning(self):
        b = make_block_b(revenue_p10=20_000_000, revenue_p50=25_000_000)
        r = _vb(b)
        codes = [i['code'] for i in r['issues']]
        assert 'HIGH_UNCERTAINTY' not in codes

    def test_short_forecast_skips_trend_check(self):
        b = make_block_b(demand_score=55, monthly_forecast_12=[10_000_000] * 4)
        r = _vb(b)
        codes = [i['code'] for i in r['issues']]
        assert 'DECLINING_TREND' not in codes


# ── Block C ───────────────────────────────────────────────────────────────────

class TestValidateBlockC:
    def test_healthy_block_no_issues(self):
        b = make_block_c(location_score=72, competitors_300m=[], anchor_effect_score=55)
        r = _vc(b)
        assert r['error_count'] == 0
        assert r['warn_count'] == 0

    def test_very_low_location_is_error(self):
        b = make_block_c(location_score=30)
        r = _vc(b)
        codes = [i['code'] for i in r['issues']]
        assert 'VERY_LOW_LOCATION' in codes

    def test_low_location_is_warning(self):
        b = make_block_c(location_score=45)
        r = _vc(b)
        levels = {i['code']: i['level'] for i in r['issues']}
        assert levels.get('LOW_LOCATION') == 'warning'
        assert 'VERY_LOW_LOCATION' not in levels

    def test_location_exactly_35_no_error(self):
        b = make_block_c(location_score=35)
        r = _vc(b)
        codes = [i['code'] for i in r['issues']]
        assert 'VERY_LOW_LOCATION' not in codes

    def test_five_competitors_300m_is_error(self):
        comps = [{'name': f'C{i}', 'distance_m': 100} for i in range(5)]
        b = make_block_c(competitors_300m=comps)
        r = _vc(b)
        codes = [i['code'] for i in r['issues']]
        assert 'TOO_MANY_NEARBY_COMPS' in codes

    def test_four_competitors_300m_no_error(self):
        comps = [{'name': f'C{i}', 'distance_m': 100} for i in range(4)]
        b = make_block_c(competitors_300m=comps)
        r = _vc(b)
        codes = [i['code'] for i in r['issues']]
        assert 'TOO_MANY_NEARBY_COMPS' not in codes

    def test_low_anchor_is_warning(self):
        b = make_block_c(anchor_effect_score=20)
        r = _vc(b)
        codes = [i['code'] for i in r['issues']]
        assert 'LOW_ANCHOR_EFFECT' in codes

    def test_anchor_exactly_25_no_warning(self):
        b = make_block_c(anchor_effect_score=25)
        r = _vc(b)
        codes = [i['code'] for i in r['issues']]
        assert 'LOW_ANCHOR_EFFECT' not in codes


# ── Block D ───────────────────────────────────────────────────────────────────

class TestValidateBlockD:
    def test_healthy_block_no_issues(self):
        b = make_block_d(
            mc_success_probability=65, breakeven_months=20,
            roi_12mo=20, ltv_cac_ratio=3.5,
            cash_flow_monthly_24=[100] * 24
        )
        r = _vd(b)
        assert r['error_count'] == 0
        assert r['warn_count'] == 0

    def test_low_success_prob_is_error(self):
        b = make_block_d(mc_success_probability=35)
        r = _vd(b)
        codes = [i['code'] for i in r['issues']]
        assert 'LOW_SUCCESS_PROB' in codes

    def test_marginal_success_prob_is_warning(self):
        b = make_block_d(mc_success_probability=50)
        r = _vd(b)
        levels = {i['code']: i['level'] for i in r['issues']}
        assert levels.get('MARGINAL_SUCCESS_PROB') == 'warning'

    def test_very_long_bep_is_error(self):
        b = make_block_d(breakeven_months=60)
        r = _vd(b)
        codes = [i['code'] for i in r['issues']]
        assert 'VERY_LONG_BEP' in codes

    def test_long_bep_is_warning(self):
        b = make_block_d(breakeven_months=40)
        r = _vd(b)
        levels = {i['code']: i['level'] for i in r['issues']}
        assert levels.get('LONG_BEP') == 'warning'

    def test_bep_exactly_48_no_error(self):
        b = make_block_d(breakeven_months=48)
        r = _vd(b)
        codes = [i['code'] for i in r['issues']]
        assert 'VERY_LONG_BEP' not in codes

    def test_negative_roi_is_error(self):
        b = make_block_d(roi_12mo=-5)
        r = _vd(b)
        codes = [i['code'] for i in r['issues']]
        assert 'NEGATIVE_ROI' in codes

    def test_zero_roi_no_error(self):
        b = make_block_d(roi_12mo=0)
        r = _vd(b)
        codes = [i['code'] for i in r['issues']]
        assert 'NEGATIVE_ROI' not in codes

    def test_poor_ltv_cac_is_warning(self):
        b = make_block_d(ltv_cac_ratio=0.5)
        r = _vd(b)
        codes = [i['code'] for i in r['issues']]
        assert 'POOR_LTV_CAC' in codes

    def test_ltv_cac_zero_no_warning(self):
        b = make_block_d(ltv_cac_ratio=0)
        r = _vd(b)
        codes = [i['code'] for i in r['issues']]
        assert 'POOR_LTV_CAC' not in codes

    def test_persistent_negative_cash_flow_is_error(self):
        cf = [100_000] * 18 + [-1_000_000, -1_000_000, -1_000_000,
                                -1_000_000, -1_000_000, -1_000_000]
        b = make_block_d(cash_flow_monthly_24=cf)
        r = _vd(b)
        codes = [i['code'] for i in r['issues']]
        assert 'PERSISTENT_NEGATIVE_CF' in codes

    def test_positive_cash_flow_at_end_no_error(self):
        cf = [-5_000_000] * 18 + [1_000_000, 1_500_000, 2_000_000,
                                   2_500_000, 3_000_000, 3_500_000]
        b = make_block_d(cash_flow_monthly_24=cf)
        r = _vd(b)
        codes = [i['code'] for i in r['issues']]
        assert 'PERSISTENT_NEGATIVE_CF' not in codes


# ── Block E ───────────────────────────────────────────────────────────────────

class TestValidateBlockE:
    def test_healthy_block_no_issues(self):
        b = make_block_e(market_risk_score=45, district_churn_rate=20, competitors_300m=[])
        r = _ve(b)
        assert r['error_count'] == 0
        assert r['warn_count'] == 0

    def test_very_high_risk_is_error(self):
        b = make_block_e(market_risk_score=80)
        r = _ve(b)
        codes = [i['code'] for i in r['issues']]
        assert 'VERY_HIGH_MARKET_RISK' in codes

    def test_high_risk_is_warning(self):
        b = make_block_e(market_risk_score=65)
        r = _ve(b)
        levels = {i['code']: i['level'] for i in r['issues']}
        assert levels.get('HIGH_MARKET_RISK') == 'warning'
        assert 'VERY_HIGH_MARKET_RISK' not in levels

    def test_risk_exactly_75_no_error(self):
        b = make_block_e(market_risk_score=75)
        r = _ve(b)
        codes = [i['code'] for i in r['issues']]
        assert 'VERY_HIGH_MARKET_RISK' not in codes

    def test_high_churn_is_warning(self):
        b = make_block_e(district_churn_rate=40)
        r = _ve(b)
        codes = [i['code'] for i in r['issues']]
        assert 'HIGH_CHURN_RATE' in codes

    def test_churn_exactly_35_no_warning(self):
        b = make_block_e(district_churn_rate=35)
        r = _ve(b)
        codes = [i['code'] for i in r['issues']]
        assert 'HIGH_CHURN_RATE' not in codes

    def test_six_competitors_300m_is_error(self):
        comps = [{'name': f'C{i}'} for i in range(6)]
        b = make_block_e(competitors_300m=comps)
        r = _ve(b)
        codes = [i['code'] for i in r['issues']]
        assert 'SEVERE_COMPETITION' in codes

    def test_five_competitors_300m_no_error(self):
        comps = [{'name': f'C{i}'} for i in range(5)]
        b = make_block_e(competitors_300m=comps)
        r = _ve(b)
        codes = [i['code'] for i in r['issues']]
        assert 'SEVERE_COMPETITION' not in codes


# ── _collect_all_validations ──────────────────────────────────────────────────

class TestCollectAllValidations:
    def _fn(self, *args):
        from apps.core.tasks import _collect_all_validations
        return _collect_all_validations(*args)

    def test_clean_blocks_produce_empty_lists(self):
        ba = make_block_a()
        bb = make_block_b()
        bc = make_block_c()
        bd = make_block_d(cash_flow_monthly_24=[100] * 24)
        be = make_block_e()
        # Inject pre-saved validation with no issues
        for b in (ba, bb, bc, bd, be):
            b.raw_data = {'validation': {'issues': [], 'error_count': 0, 'warn_count': 0}}
        r = self._fn(ba, bb, bc, bd, be)
        assert r['errors'] == []
        assert r['warnings'] == []

    def test_errors_from_multiple_blocks_aggregated(self):
        ba = make_block_a()
        ba.raw_data = {'validation': {'issues': [
            {'level': 'error', 'code': 'X', 'message': 'msg A error'}
        ]}}
        bd = make_block_d()
        bd.raw_data = {'validation': {'issues': [
            {'level': 'error', 'code': 'Y', 'message': 'msg D error'}
        ]}}
        for b in (make_block_b(), make_block_c(), make_block_e()):
            b.raw_data = {}
        r = self._fn(ba, make_block_b(), make_block_c(), bd, make_block_e())
        assert len(r['errors']) == 2
        assert any('[A]' in e for e in r['errors'])
        assert any('[D]' in e for e in r['errors'])

    def test_none_blocks_skipped_safely(self):
        r = self._fn(None, None, None, None, None)
        assert r['errors'] == []
        assert r['warnings'] == []
