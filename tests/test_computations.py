"""
Unit tests for pure computation functions in tasks.py.
No database access — all functions are stateless math.
"""
import pytest
import sys
import os

# Allow importing from project root without Django setup for pure functions
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── _compare ──────────────────────────────────────────────────────────────────

class TestCompare:
    def _fn(self, *args, **kwargs):
        from apps.core.tasks import _compare
        return _compare(*args, **kwargs)

    def test_perfect_match_is_zero_diff(self):
        r = self._fn(1000.0, 1000.0, 'label')
        assert r['diff_pct'] == 0.0
        assert r['risk'] == 'low'

    def test_over_estimate_positive_diff(self):
        r = self._fn(150.0, 100.0, 'label')
        assert r['diff_pct'] == 50.0
        assert r['risk'] == 'medium'

    def test_under_estimate_negative_diff(self):
        r = self._fn(50.0, 100.0, 'label')
        assert r['diff_pct'] == -50.0
        assert r['risk'] == 'medium'

    def test_large_diff_is_high_risk(self):
        r = self._fn(0.0, 100.0, 'label')
        assert abs(r['diff_pct']) > 50
        assert r['risk'] == 'high'

    def test_small_diff_is_low_risk(self):
        r = self._fn(105.0, 100.0, 'label')
        assert r['risk'] == 'low'

    def test_zero_ai_val_returns_zero_diff(self):
        r = self._fn(500.0, 0.0, 'label')
        assert r['diff_pct'] == 0.0

    def test_label_preserved(self):
        r = self._fn(10.0, 10.0, 'My Label')
        assert r['label'] == 'My Label'

    def test_values_are_rounded(self):
        r = self._fn(100.3, 100.7, 'label')
        assert isinstance(r['user'], int)
        assert isinstance(r['ai'], int)

    def test_risk_boundary_exactly_20_is_low(self):
        r = self._fn(120.0, 100.0, 'label')
        assert r['risk'] == 'low'

    def test_risk_boundary_just_above_20_is_medium(self):
        r = self._fn(121.0, 100.0, 'label')
        assert r['risk'] == 'medium'

    def test_risk_boundary_exactly_50_is_medium(self):
        r = self._fn(150.0, 100.0, 'label')
        assert r['risk'] == 'medium'

    def test_risk_boundary_just_above_50_is_high(self):
        r = self._fn(151.0, 100.0, 'label')
        assert r['risk'] == 'high'


# ── _compute_viability_score ───────────────────────────────────────────────────

class TestComputeViabilityScore:
    def _fn(self, *args, **kwargs):
        from apps.core.tasks import _compute_viability_score
        return _compute_viability_score(*args, **kwargs)

    def test_ideal_inputs_near_100(self):
        score = self._fn(bep_months=8, roi_12=35, mc_success_prob=90, ltv_cac=6)
        assert score >= 90

    def test_terrible_inputs_low_score(self):
        score = self._fn(bep_months=60, roi_12=-10, mc_success_prob=20, ltv_cac=0)
        assert score < 25

    def test_score_is_capped_at_100(self):
        score = self._fn(bep_months=1, roi_12=100, mc_success_prob=100, ltv_cac=10)
        assert score <= 100.0

    def test_score_is_non_negative(self):
        score = self._fn(bep_months=999, roi_12=-50, mc_success_prob=0, ltv_cac=0)
        assert score >= 0.0

    def test_bep_12_contribution(self):
        """BEP < 12 months should give 35 points."""
        s_good = self._fn(bep_months=10, roi_12=0, mc_success_prob=0, ltv_cac=0)
        s_bad = self._fn(bep_months=50, roi_12=0, mc_success_prob=0, ltv_cac=0)
        assert s_good > s_bad

    def test_roi_contribution(self):
        s_high = self._fn(bep_months=30, roi_12=35, mc_success_prob=50, ltv_cac=0)
        s_low = self._fn(bep_months=30, roi_12=3, mc_success_prob=50, ltv_cac=0)
        assert s_high > s_low

    def test_mc_success_prob_scales_linearly(self):
        s80 = self._fn(bep_months=30, roi_12=10, mc_success_prob=80, ltv_cac=0)
        s40 = self._fn(bep_months=30, roi_12=10, mc_success_prob=40, ltv_cac=0)
        assert s80 - s40 == pytest.approx((80 - 40) * 0.20, abs=1)

    def test_ltv_cac_above_5(self):
        s_great = self._fn(bep_months=30, roi_12=10, mc_success_prob=50, ltv_cac=6)
        s_zero = self._fn(bep_months=30, roi_12=10, mc_success_prob=50, ltv_cac=0)
        assert s_great - s_zero == 15


# ── _generate_forecast ─────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestGenerateForecast:
    def _fn(self, history, months=12, mcc_code='5812'):
        from apps.core.tasks import _generate_forecast
        return _generate_forecast(history, months, mcc_code)

    def test_returns_three_lists(self):
        f, lo, hi = self._fn([30_000_000] * 12)
        assert len(f) == 12
        assert len(lo) == 12
        assert len(hi) == 12

    def test_36_month_forecast_length(self):
        f, _, _ = self._fn([30_000_000] * 12, months=36)
        assert len(f) == 36

    def test_all_values_non_negative(self):
        f, lo, hi = self._fn([30_000_000] * 12)
        assert all(v >= 0 for v in f)
        assert all(v >= 0 for v in lo)
        assert all(v >= 0 for v in hi)

    def test_confidence_band_ordering(self):
        f, lo, hi = self._fn([30_000_000] * 12)
        for fl, fv, fh in zip(lo, f, hi):
            assert fl <= fv + 1  # low <= forecast (+1 for float rounding)
            assert fv <= fh + 1  # forecast <= high

    def test_empty_history_uses_default_base(self):
        f, _, _ = self._fn([])
        assert all(v > 0 for v in f)

    def test_growing_history_produces_positive_trend(self):
        growing = [10_000_000 * (i + 1) for i in range(12)]
        f, _, _ = self._fn(growing, months=3)
        # Last forecast should be larger than first given upward trend
        assert f[-1] > f[0]


# ── _hourly_footfall_curve ────────────────────────────────────────────────────

class TestHourlyFootfallCurve:
    def _fn(self, mcc_code):
        from apps.core.tasks import _hourly_footfall_curve
        return _hourly_footfall_curve(mcc_code)

    def test_returns_24_values(self):
        assert len(self._fn('5812')) == 24
        assert len(self._fn('5411')) == 24
        assert len(self._fn('9999')) == 24

    def test_all_values_positive(self):
        for code in ('5812', '5411', '1234'):
            assert all(v > 0 for v in self._fn(code))

    def test_cafe_peak_is_lunchtime_or_evening(self):
        curve = self._fn('5812')
        peak_hour = curve.index(max(curve))
        assert 11 <= peak_hour <= 20

    def test_grocery_peak_is_evening(self):
        curve = self._fn('5411')
        peak_hour = curve.index(max(curve))
        assert 15 <= peak_hour <= 20
