"""
Unit tests for ScoringEngine — composite score, thresholds, credit tiers,
weight integrity, and derive_block_scores.
"""
import pytest
from tests.conftest import (
    make_block_a, make_block_b, make_block_c,
    make_block_d, make_block_e,
)


class TestScoringEngineWeights:
    def test_weights_sum_to_one(self):
        from services.scoring_engine import ScoringEngine
        total = sum(ScoringEngine.WEIGHTS.values())
        assert total == pytest.approx(1.0, abs=1e-9)

    def test_weights_cover_all_blocks(self):
        from services.scoring_engine import ScoringEngine
        assert set(ScoringEngine.WEIGHTS.keys()) == {'A', 'B', 'C', 'D', 'E'}

    def test_c_and_d_have_highest_weights(self):
        from services.scoring_engine import ScoringEngine
        w = ScoringEngine.WEIGHTS
        assert w['C'] >= 0.20
        assert w['D'] >= 0.20


class TestComputeComposite:
    def _engine(self):
        from services.scoring_engine import ScoringEngine
        return ScoringEngine()

    def test_all_100_scores_gives_100(self):
        r = self._engine().compute_composite({'A': 100, 'B': 100, 'C': 100, 'D': 100, 'E': 100})
        assert r['composite_score'] == 100.0

    def test_all_zero_scores_gives_zero(self):
        r = self._engine().compute_composite({'A': 0, 'B': 0, 'C': 0, 'D': 0, 'E': 0})
        assert r['composite_score'] == 0.0

    def test_score_is_capped_at_100(self):
        r = self._engine().compute_composite({'A': 200, 'B': 200, 'C': 200, 'D': 200, 'E': 200})
        assert r['composite_score'] <= 100.0

    def test_score_is_non_negative(self):
        r = self._engine().compute_composite({'A': -50, 'B': -50, 'C': -50, 'D': -50, 'E': -50})
        assert r['composite_score'] >= 0.0

    def test_missing_blocks_default_to_zero(self):
        r = self._engine().compute_composite({'A': 80})
        # Only A contributes (weight 0.20 → 16 points)
        assert r['composite_score'] == pytest.approx(80 * 0.20, abs=0.1)

    def test_weighted_calculation_correct(self):
        from services.scoring_engine import ScoringEngine
        w = ScoringEngine.WEIGHTS
        scores = {'A': 80, 'B': 70, 'C': 65, 'D': 75, 'E': 60}
        expected = sum(scores[k] * w[k] for k in w)
        r = self._engine().compute_composite(scores)
        assert r['composite_score'] == pytest.approx(expected, abs=0.01)

    def test_result_has_required_keys(self):
        r = self._engine().compute_composite({'A': 70, 'B': 70, 'C': 70, 'D': 70, 'E': 70})
        for key in ('composite_score', 'recommendation', 'credit_tier', 'breakdown'):
            assert key in r

    def test_breakdown_has_all_blocks(self):
        r = self._engine().compute_composite({'A': 70, 'B': 70, 'C': 70, 'D': 70, 'E': 70})
        assert set(r['breakdown'].keys()) == {'A', 'B', 'C', 'D', 'E'}

    def test_breakdown_contribution_matches_weight_times_score(self):
        from services.scoring_engine import ScoringEngine
        r = self._engine().compute_composite({'A': 80, 'B': 0, 'C': 0, 'D': 0, 'E': 0})
        a_contrib = r['breakdown']['A']['contribution']
        assert a_contrib == pytest.approx(80 * ScoringEngine.WEIGHTS['A'], abs=0.01)


class TestRecommendationThresholds:
    def _rec(self, score):
        from services.scoring_engine import ScoringEngine
        eng = ScoringEngine()
        # Build scores that yield the target composite by setting all to score
        r = eng.compute_composite({'A': score, 'B': score, 'C': score, 'D': score, 'E': score})
        return r['recommendation']

    def test_70_or_above_is_yes(self):
        assert self._rec(70) == 'YES'
        assert self._rec(85) == 'YES'
        assert self._rec(100) == 'YES'

    def test_45_to_69_is_caution(self):
        assert self._rec(45) == 'CAUTION'
        assert self._rec(60) == 'CAUTION'
        assert self._rec(69) == 'CAUTION'

    def test_below_45_is_no(self):
        assert self._rec(0) == 'NO'
        assert self._rec(30) == 'NO'
        assert self._rec(44) == 'NO'

    def test_boundary_70_is_yes_not_caution(self):
        assert self._rec(70) == 'YES'

    def test_boundary_45_is_caution_not_no(self):
        assert self._rec(45) == 'CAUTION'


class TestCreditTiers:
    def _tier(self, score):
        from services.scoring_engine import ScoringEngine
        return ScoringEngine._score_to_credit_tier(score)

    def test_80_plus_is_excellent(self):
        assert self._tier(80) == 'Excellent'
        assert self._tier(95) == 'Excellent'
        assert self._tier(100) == 'Excellent'

    def test_65_to_79_is_good(self):
        assert self._tier(65) == 'Good'
        assert self._tier(72) == 'Good'
        assert self._tier(79) == 'Good'

    def test_45_to_64_is_moderate(self):
        assert self._tier(45) == 'Moderate'
        assert self._tier(55) == 'Moderate'
        assert self._tier(64) == 'Moderate'

    def test_below_45_is_high_risk(self):
        assert self._tier(0) == 'High Risk'
        assert self._tier(30) == 'High Risk'
        assert self._tier(44) == 'High Risk'


class TestDeriveBlockScores:
    def test_all_none_returns_empty_dict(self):
        from services.scoring_engine import ScoringEngine
        r = ScoringEngine.derive_block_scores()
        assert r == {}

    def test_block_a_maps_to_niche_opportunity_score(self):
        from services.scoring_engine import ScoringEngine
        ba = make_block_a(niche_opportunity_score=72)
        r = ScoringEngine.derive_block_scores(block_a=ba)
        assert r['A'] == 72

    def test_block_b_maps_to_demand_score(self):
        from services.scoring_engine import ScoringEngine
        bb = make_block_b(demand_score=65)
        r = ScoringEngine.derive_block_scores(block_b=bb)
        assert r['B'] == 65

    def test_block_c_maps_to_location_score(self):
        from services.scoring_engine import ScoringEngine
        bc = make_block_c(location_score=78)
        r = ScoringEngine.derive_block_scores(block_c=bc)
        assert r['C'] == 78

    def test_block_d_maps_to_viability_score(self):
        from services.scoring_engine import ScoringEngine
        bd = make_block_d(viability_score=70)
        r = ScoringEngine.derive_block_scores(block_d=bd)
        assert r['D'] == 70

    def test_block_e_maps_to_market_risk_score_inv(self):
        from services.scoring_engine import ScoringEngine
        be = make_block_e(market_risk_score_inv=58)
        r = ScoringEngine.derive_block_scores(block_e=be)
        assert r['E'] == 58

    def test_all_blocks_present(self):
        from services.scoring_engine import ScoringEngine
        r = ScoringEngine.derive_block_scores(
            block_a=make_block_a(),
            block_b=make_block_b(),
            block_c=make_block_c(),
            block_d=make_block_d(),
            block_e=make_block_e(),
        )
        assert set(r.keys()) == {'A', 'B', 'C', 'D', 'E'}
