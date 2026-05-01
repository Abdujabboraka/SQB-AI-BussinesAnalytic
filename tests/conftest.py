"""
Shared fixtures and mock helpers for all test modules.
"""
import pytest
from unittest.mock import MagicMock

# ── Mock AI response payloads ─────────────────────────────────────────────────

MOCK_BLOCK_A_AI = {
    'tam_uzs': 50_000_000_000,
    'sam_uzs': 17_500_000_000,
    'som_uzs': 4_000_000_000,
    'saturation_index': 0.55,
    'gap_score': 60.0,
    'niche_opportunity_score': 65.0,
    'commentary': 'Bozor imkoniyati mavjud.',
    'is_mock': False,
}

MOCK_BLOCK_B_AI = {
    'demand_score': 68.0,
    'commentary': 'Talab yaxshi.',
    'is_mock': False,
}

MOCK_BLOCK_C_AI = {
    'location_score': 72.0,
    'isochrone_demand_5min': 3500,
    'isochrone_demand_10min': 12000,
    'anchor_effect_score': 55.0,
    'commentary': 'Joylashuv qulay.',
    'is_mock': False,
}

MOCK_BLOCK_D_AI = {
    'viability_score': 65.0,
    'commentary': 'Moliyaviy ko\'rsatkichlar qoniqarli.',
    'is_mock': False,
}

MOCK_BLOCK_E_AI = {
    'market_risk_score': 42.0,
    'entry_barriers': ['Kapital talab', 'Litsenziya'],
    'closure_probabilities': {},
    'recommendation_notes': 'Raqobat o\'rtacha.',
    'commentary': 'Xavf boshqariladigan darajada.',
    'is_mock': False,
}

MOCK_FINAL_AI = {
    'recommendation': 'YES',
    'commentary': 'Biznes uchun qulay sharoit.',
    'credit_tier': 'Good',
    'is_mock': False,
}


# ── Block result mock builders ────────────────────────────────────────────────

def make_block_a(
    saturation_index=0.55,
    niche_opportunity_score=65.0,
    som_uzs=4_000_000_000,
    gap_score=60.0,
):
    m = MagicMock()
    m.saturation_index = saturation_index
    m.niche_opportunity_score = niche_opportunity_score
    m.som_uzs = som_uzs
    m.gap_score = gap_score
    m.raw_data = {}
    return m


def make_block_b(
    demand_score=68.0,
    monthly_forecast_12=None,
    revenue_p10=20_000_000,
    revenue_p50=35_000_000,
    revenue_p90=55_000_000,
):
    m = MagicMock()
    m.demand_score = demand_score
    m.monthly_forecast_12 = monthly_forecast_12 or [35_000_000] * 12
    m.revenue_p10 = revenue_p10
    m.revenue_p50 = revenue_p50
    m.revenue_p90 = revenue_p90
    m.raw_data = {}
    return m


def make_block_c(
    location_score=72.0,
    competitors_300m=None,
    anchor_effect_score=55.0,
):
    m = MagicMock()
    m.location_score = location_score
    m.competitors_300m = competitors_300m or []
    m.anchor_effect_score = anchor_effect_score
    m.raw_data = {}
    return m


def make_block_d(
    viability_score=65.0,
    mc_success_probability=62.0,
    breakeven_months=22.0,
    roi_12mo=18.5,
    ltv_cac_ratio=3.2,
    cash_flow_monthly_24=None,
):
    m = MagicMock()
    m.viability_score = viability_score
    m.mc_success_probability = mc_success_probability
    m.breakeven_months = breakeven_months
    m.roi_12mo = roi_12mo
    m.ltv_cac_ratio = ltv_cac_ratio
    m.cash_flow_monthly_24 = cash_flow_monthly_24 or ([None] * 18 + [1, 2, 3, 4, 5, 6])
    m.raw_data = {}
    return m


def make_block_e(
    market_risk_score=42.0,
    market_risk_score_inv=58.0,
    district_churn_rate=20.0,
    competitors_300m=None,
):
    m = MagicMock()
    m.market_risk_score = market_risk_score
    m.market_risk_score_inv = market_risk_score_inv
    m.district_churn_rate = district_churn_rate
    m.competitors_300m = competitors_300m or []
    m.raw_data = {}
    return m


def make_mock_request(
    business_type='Kafe',
    district='Yunusobod',
    mcc_code='5812',
    investment_amount=500_000_000,
    target_monthly_revenue=40_000_000,
    expected_daily_customers=80,
    average_check_uzs=50_000,
    working_days_per_week=7,
    monthly_fixed_costs=8_000_000,
    variable_cost_pct=35.0,
    planned_markup_pct=60.0,
    latitude=41.299496,
    longitude=69.240073,
    foot_traffic='high',
    known_competitors=2,
    loan_amount=300_000_000,
    own_capital=200_000_000,
):
    m = MagicMock()
    m.business_type = business_type
    m.district = district
    m.mcc_code = mcc_code
    m.investment_amount = investment_amount
    m.target_monthly_revenue = target_monthly_revenue
    m.expected_daily_customers = expected_daily_customers
    m.average_check_uzs = average_check_uzs
    m.working_days_per_week = working_days_per_week
    m.monthly_fixed_costs = monthly_fixed_costs
    m.variable_cost_pct = variable_cost_pct
    m.planned_markup_pct = planned_markup_pct
    m.latitude = latitude
    m.longitude = longitude
    m.foot_traffic = foot_traffic
    m.known_competitors = known_competitors
    m.loan_amount = loan_amount
    m.own_capital = own_capital
    m.cogs_percentage = 0
    m.monthly_rent_uzs = 0
    m.monthly_salary_budget = 0
    m.monthly_utilities = 0
    m.business_category_type = 'general'
    m.computed_monthly_fixed_costs = monthly_fixed_costs
    return m
