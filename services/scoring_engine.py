"""
Scoring Engine — two classes:
1. ScoringEngine  : existing A-E block composite scorer (unchanged)
2. SQBCreditScorer: SQB Bank-aligned credit decision engine
                    supporting all 4 business categories
"""
from django.conf import settings


class ScoringEngine:
    WEIGHTS = {
        'A': 0.20,  # Market Analysis
        'B': 0.20,  # Demand Forecast
        'C': 0.25,  # Location Intel
        'D': 0.25,  # Financial Viability
        'E': 0.10,  # Competition Risk (inverted)
    }

    def compute_composite(self, block_scores: dict) -> dict:
        score = sum(
            block_scores.get(k, 0) * w
            for k, w in self.WEIGHTS.items()
        )
        score = round(min(100.0, max(0.0, score)), 2)

        if score >= 70:
            recommendation = 'YES'
        elif score >= 45:
            recommendation = 'CAUTION'
        else:
            recommendation = 'NO'

        credit_tier = self._score_to_credit_tier(score)

        breakdown = {
            k: {
                'raw_score': round(block_scores.get(k, 0), 1),
                'weight': self.WEIGHTS[k],
                'contribution': round(block_scores.get(k, 0) * self.WEIGHTS[k], 2),
            }
            for k in self.WEIGHTS
        }

        return {
            'composite_score': score,
            'recommendation': recommendation,
            'credit_tier': credit_tier,
            'breakdown': breakdown,
        }

    @staticmethod
    def _score_to_credit_tier(score: float) -> str:
        if score >= 80:
            return 'Excellent'
        elif score >= 65:
            return 'Good'
        elif score >= 45:
            return 'Moderate'
        else:
            return 'High Risk'

    @staticmethod
    def derive_block_scores(block_a=None, block_b=None, block_c=None,
                             block_d=None, block_e=None) -> dict:
        scores = {}
        if block_a:
            scores['A'] = block_a.niche_opportunity_score
        if block_b:
            scores['B'] = block_b.demand_score
        if block_c:
            scores['C'] = block_c.location_score
        if block_d:
            scores['D'] = block_d.viability_score
        if block_e:
            scores['E'] = block_e.market_risk_score_inv
        return scores


# ══════════════════════════════════════════════════════════════
# SQB CREDIT SCORER — Bank-aligned decision engine
# ══════════════════════════════════════════════════════════════

class SQBCreditScorer:
    """
    SQB Bank credit assessment per CBU 2025 requirements.
    Supports 4 business categories with category-specific weights.
    """

    # SQB / CBU 2025 thresholds
    MIN_DSC_RATIO = 1.25          # Debt Service Coverage >= 1.25
    MAX_DEBT_BURDEN_PCT = 50.0    # Income debt load <= 50%
    MIN_COLLATERAL_COVERAGE = 1.25
    MIN_OWN_CAPITAL_PCT = 20.0    # Own capital >= 20%

    CATEGORY_WEIGHTS = {
        'hotel':        {'location': 0.35, 'finance': 0.35, 'risk': 0.30},
        'construction': {'timeline': 0.40, 'finance': 0.35, 'market': 0.25},
        'textile':      {'export':   0.35, 'finance': 0.35, 'supply': 0.30},
        'trade':        {'location': 0.40, 'turnover': 0.35, 'finance': 0.25},
        'general':      {'A': 0.20,  'B': 0.20, 'C': 0.25, 'D': 0.25, 'E': 0.10},
    }

    # SQB credit decisions
    DECISION_MAP = [
        (75, "TASDIQLASH TAVSIYA ETILADI", "green"),
        (55, "QO'SHIMCHA TAHLIL KERAK",    "yellow"),
        (40, "SHARTLI TASDIQLASH",         "orange"),
        (0,  "RAD ETISH TAVSIYA ETILADI",  "red"),
    ]

    # ── Core financial checks ─────────────────────────────────

    def calculate_dsc_ratio(self, monthly_net_income: float, monthly_debt_payment: float) -> float:
        """Debt Service Coverage Ratio. CBU 2025: must be >= 1.25"""
        if monthly_debt_payment <= 0:
            return 99.0
        return round(monthly_net_income / monthly_debt_payment, 2)

    def calculate_collateral_coverage(self, collateral_value: float, loan_amount: float) -> float:
        """Collateral coverage ratio. SQB requires >= 1.25"""
        if loan_amount <= 0:
            return 99.0
        return round(collateral_value / loan_amount, 2)

    def calculate_debt_burden_pct(self, total_monthly_debt: float, monthly_income: float) -> float:
        """Qarz yuki = jami oylik kredit to'lovi / oylik daromad × 100. Max 50%."""
        if monthly_income <= 0:
            return 100.0
        return round((total_monthly_debt / monthly_income) * 100, 1)

    # ── Component scorers ─────────────────────────────────────

    def score_financial_health(self, req, monthly_revenue: float) -> float:
        """30% weight — financial ratios (all categories)"""
        score = 0.0

        # 1. Own capital share (0-30)
        inv = float(req.investment_amount or 1)
        own = float(req.own_capital or 0)
        own_pct = (own / inv * 100) if inv > 0 else 0
        if own_pct >= 40:
            score += 30
        elif own_pct >= 30:
            score += 22
        elif own_pct >= self.MIN_OWN_CAPITAL_PCT:
            score += 14
        else:
            score += 5

        # 2. Debt burden estimate (0-35)
        loan = float(req.loan_amount or 0)
        loan_term = float(getattr(req, 'desired_payback_months', 24) or 24)
        monthly_payment = (loan / loan_term) * 1.24 if loan_term > 0 else 0  # ~24% interest
        debt_burden = self.calculate_debt_burden_pct(monthly_payment, monthly_revenue)
        if debt_burden <= 30:
            score += 35
        elif debt_burden <= self.MAX_DEBT_BURDEN_PCT:
            score += 25
        elif debt_burden <= 65:
            score += 10

        # 3. DSC ratio (0-35)
        fixed_costs = float(req.computed_monthly_fixed_costs)
        net_income = monthly_revenue - fixed_costs
        dsc = self.calculate_dsc_ratio(net_income, monthly_payment)
        if dsc >= 2.0:
            score += 35
        elif dsc >= self.MIN_DSC_RATIO:
            score += 25
        elif dsc >= 1.0:
            score += 10

        return min(100.0, score)

    def score_collateral(self, req) -> float:
        """25% weight — collateral quality"""
        score = 0.0
        loan = float(req.loan_amount or 0)
        if loan <= 0:
            return 80.0

        # Estimate collateral from real estate + equipment
        investment = float(req.investment_amount or 0)
        own = float(req.own_capital or 0)
        # Assume own capital partly in real estate (80% of own capital)
        collateral_est = own * 0.8
        coverage = self.calculate_collateral_coverage(collateral_est, loan)

        if coverage >= 2.0:
            score = 90
        elif coverage >= 1.5:
            score = 75
        elif coverage >= self.MIN_COLLATERAL_COVERAGE:
            score = 55
        elif coverage >= 1.0:
            score = 30
        else:
            score = 10

        # Experience bonus
        exp = getattr(req, 'market_experience_years', 0) or 0
        if exp >= 5:
            score = min(100, score + 10)
        elif exp >= 3:
            score = min(100, score + 5)

        return score

    # ── Category-specific scorers ─────────────────────────────

    def score_hotel_category(self, req) -> float:
        """Location + tourist flow score for hotels"""
        try:
            detail = req.hotel_detail
        except Exception:
            return 50.0

        score = 0.0
        # Distance to airport
        dist_airport = detail.distance_to_airport_km
        if dist_airport <= 10:
            score += 25
        elif dist_airport <= 20:
            score += 18
        elif dist_airport <= 35:
            score += 10

        # Distance to attraction
        dist_att = detail.distance_to_top_attraction_km
        if dist_att <= 0.5:
            score += 30
        elif dist_att <= 2:
            score += 22
        elif dist_att <= 5:
            score += 12

        # Occupancy target realism
        occ = detail.target_occupancy_pct
        if 60 <= occ <= 80:
            score += 25
        elif 50 <= occ < 60 or 80 < occ <= 90:
            score += 15

        # Subsidy / franchise bonus
        if detail.franchise_agreement:
            score += 15
        if detail.applying_for_subsidy:
            score += 5

        return min(100.0, score)

    def score_construction_category(self, req) -> float:
        """Timeline risk score for construction"""
        try:
            detail = req.construction_detail
        except Exception:
            return 40.0

        score = 0.0

        # License status (critical — no license = blocked)
        if detail.has_license:
            score += 40
        elif detail.months_to_get_license <= 3:
            score += 20
        elif detail.months_to_get_license <= 6:
            score += 10

        # Time to first income (lower = better)
        ttfi = detail.months_to_first_income
        if ttfi <= 4:
            score += 30
        elif ttfi <= 8:
            score += 20
        elif ttfi <= 12:
            score += 10

        # Contract pipeline
        has_contracts = bool(detail.current_contracts and len(detail.current_contracts) > 20)
        if has_contracts:
            score += 20
        has_pipeline = bool(detail.pipeline_projects and len(detail.pipeline_projects) > 20)
        if has_pipeline:
            score += 10

        return min(100.0, score)

    def score_textile_category(self, req) -> float:
        """Export readiness score for textile"""
        try:
            detail = req.textile_detail
        except Exception:
            return 40.0

        score = 0.0

        # Certifications
        certs = detail.certifications or []
        if 'gots' in certs or 'oeko_tex' in certs:
            score += 30
        elif 'iso_9001' in certs or 'bci' in certs:
            score += 18
        elif certs and 'none' not in certs:
            score += 8

        # Export experience + buyers
        if detail.export_experience:
            score += 25
        if detail.existing_buyers and len(detail.existing_buyers) > 20:
            score += 20

        # Target markets
        markets = detail.target_market or []
        premium_markets = {'eu', 'us', 'middle_east'}
        if premium_markets & set(markets):
            score += 15
        elif {'cis'} & set(markets):
            score += 8

        # Equipment age penalty
        if detail.machinery_age_years <= 5:
            score += 10
        elif detail.machinery_age_years <= 10:
            score += 5

        return min(100.0, score)

    def score_trade_category(self, req) -> float:
        """Location + turnover score for trade/retail"""
        try:
            detail = req.trade_detail
        except Exception:
            return 50.0

        score = 0.0

        # Foot traffic
        ft_map = {'very_high': 35, 'high': 25, 'medium': 15, 'low': 5}
        score += ft_map.get(detail.foot_traffic, 10)

        # Inventory turnover (lower days = better for working capital)
        itd = detail.inventory_turnover_days
        if itd <= 14:
            score += 30
        elif itd <= 30:
            score += 22
        elif itd <= 60:
            score += 12

        # Supplier credit (more days = better for cash flow)
        scd = detail.supplier_credit_days
        if scd >= 30:
            score += 20
        elif scd >= 14:
            score += 12
        elif scd >= 7:
            score += 6

        # Competition penalty
        comp = detail.direct_competitors_300m
        if comp == 0:
            score += 15
        elif comp <= 2:
            score += 10
        elif comp <= 5:
            score += 3

        return min(100.0, score)

    # ── Master scorer ─────────────────────────────────────────

    def compute(self, req, monthly_revenue: float = 0) -> dict:
        """
        Full SQB credit score for any category.
        Returns composite score + SQB verdict + component breakdown.
        """
        cat = getattr(req, 'business_category_type', 'general')

        # If no revenue provided, estimate from model fields
        if monthly_revenue <= 0:
            daily = getattr(req, 'expected_daily_customers', 50) or 50
            check = float(getattr(req, 'average_check_uzs', 50000) or 50000)
            days  = getattr(req, 'working_days_per_week', 7) or 7
            monthly_revenue = daily * check * days * 4.3

        # Component scores
        financial  = self.score_financial_health(req, monthly_revenue)
        collateral = self.score_collateral(req)

        cat_score_fn = {
            'hotel':        self.score_hotel_category,
            'construction': self.score_construction_category,
            'textile':      self.score_textile_category,
            'trade':        self.score_trade_category,
        }.get(cat)

        if cat_score_fn:
            category_score = cat_score_fn(req)
            w = self.CATEGORY_WEIGHTS.get(cat, {})
            # Compose with category-aware weights
            wf  = list(w.values())[1] if len(w) >= 2 else 0.35
            wc  = list(w.values())[0] if len(w) >= 1 else 0.35
            wr  = list(w.values())[2] if len(w) >= 3 else 0.30
            composite = (
                category_score * wc +
                financial * wf +
                collateral * wr
            )
        else:
            # General: equal weight
            composite = (financial * 0.50 + collateral * 0.50)

        composite = round(min(100.0, max(0.0, composite)), 1)

        # DSC and collateral coverage for display
        loan = float(req.loan_amount or 0)
        payback = float(getattr(req, 'desired_payback_months', 24) or 24)
        monthly_payment = (loan / payback) * 1.24 if payback > 0 else 0
        fixed = float(req.computed_monthly_fixed_costs)
        net_income = monthly_revenue - fixed
        dsc = self.calculate_dsc_ratio(net_income, monthly_payment)
        own = float(req.own_capital or 0)
        collateral_val = own * 0.8
        cov = self.calculate_collateral_coverage(collateral_val, loan)
        debt_burden = self.calculate_debt_burden_pct(monthly_payment, monthly_revenue)

        # Decision
        verdict, color = "RAD ETISH TAVSIYA ETILADI", "red"
        for threshold, label, clr in self.DECISION_MAP:
            if composite >= threshold:
                verdict, color = label, clr
                break

        # Grace period recommendation
        grace_months = 0
        if cat == 'hotel':
            grace_months = 12 if getattr(req, 'hotel_detail', None) and \
                            req.hotel_detail.applying_for_subsidy else 6
        elif cat == 'construction':
            grace_months = getattr(req, 'construction_detail', None) and \
                           req.construction_detail.months_to_first_income or 6
        elif cat == 'textile':
            grace_months = 6

        return {
            'composite_score': composite,
            'verdict': verdict,
            'verdict_color': color,
            'dsc_ratio': dsc,
            'collateral_coverage': cov,
            'debt_burden_pct': debt_burden,
            'grace_period_months': int(grace_months) if grace_months else 6,
            'category': cat,
            'breakdown': {
                'financial_score': round(financial, 1),
                'collateral_score': round(collateral, 1),
                'category_score': round(category_score if cat_score_fn else 0, 1),
                'monthly_revenue_est': int(monthly_revenue),
                'monthly_loan_payment': int(monthly_payment),
            },
            'flags': {
                'dsc_ok': dsc >= self.MIN_DSC_RATIO,
                'collateral_ok': cov >= self.MIN_COLLATERAL_COVERAGE,
                'debt_burden_ok': debt_burden <= self.MAX_DEBT_BURDEN_PCT,
                'own_capital_ok': (own / float(req.investment_amount or 1) * 100) >= self.MIN_OWN_CAPITAL_PCT,
            },
        }
