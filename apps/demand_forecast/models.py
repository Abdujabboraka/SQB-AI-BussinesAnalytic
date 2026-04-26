from django.db import models
from apps.core.models import BusinessAnalysisRequest


class BlockBResult(models.Model):
    request = models.OneToOneField(
        BusinessAnalysisRequest, on_delete=models.CASCADE, related_name='block_b'
    )
    # Forecast arrays stored as JSON lists
    monthly_forecast_12 = models.JSONField(default=list)   # 12 months
    monthly_forecast_36 = models.JSONField(default=list)   # 36 months
    confidence_low_12 = models.JSONField(default=list)
    confidence_high_12 = models.JSONField(default=list)
    # Percentiles
    revenue_p10 = models.BigIntegerField(default=0)
    revenue_p50 = models.BigIntegerField(default=0)
    revenue_p90 = models.BigIntegerField(default=0)
    # Seasonality
    seasonality_ramazon_boost_pct = models.FloatField(default=0.0)
    seasonality_navro_boost_pct = models.FloatField(default=0.0)
    seasonality_weekly = models.JSONField(default=list)    # 7 days multipliers
    # Score (0-100 derived from p50 vs investment)
    demand_score = models.FloatField(default=0.0)
    ai_commentary = models.TextField(blank=True)
    raw_data = models.JSONField(default=dict)
    is_mock = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'B Blok — Talab prognozi'

    def __str__(self):
        return f"Block B: {self.request}"
