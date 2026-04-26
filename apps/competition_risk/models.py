from django.db import models
from apps.core.models import BusinessAnalysisRequest


class BlockEResult(models.Model):
    request = models.OneToOneField(
        BusinessAnalysisRequest, on_delete=models.CASCADE, related_name='block_e'
    )
    # Competitor lists with risk data
    competitors_300m = models.JSONField(default=list)
    # [{id, name, type, lat, lng, distance_m, age_years, closure_probability}]
    competitors_1km = models.JSONField(default=list)
    # Risk analysis
    entry_barriers = models.JSONField(default=list)       # list of strings
    market_risk_score = models.FloatField(default=0.0)   # 0 – 100 (higher = riskier)
    market_risk_score_inv = models.FloatField(default=0.0)  # 100 - risk (for weighting)
    district_churn_rate = models.FloatField(default=0.0)  # % per year
    # Gemini text
    recommendation_notes = models.TextField(blank=True)
    ai_commentary = models.TextField(blank=True)
    raw_data = models.JSONField(default=dict)
    is_mock = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'E Blok — Raqobat va risklar'

    def __str__(self):
        return f"Block E: {self.request}"
