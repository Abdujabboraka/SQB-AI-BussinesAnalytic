from django.db import models
from apps.core.models import BusinessAnalysisRequest


class BlockDResult(models.Model):
    request = models.OneToOneField(
        BusinessAnalysisRequest, on_delete=models.CASCADE, related_name='block_d'
    )
    # Break-even
    breakeven_months = models.FloatField(default=0.0)
    breakeven_revenue_uzs = models.BigIntegerField(default=0)
    # Monte Carlo results
    mc_profit_distribution = models.JSONField(default=list)  # 1000 values
    mc_mean_profit = models.BigIntegerField(default=0)
    mc_std_profit = models.BigIntegerField(default=0)
    mc_success_probability = models.FloatField(default=0.0)  # % > 0
    # ROI
    roi_12mo = models.FloatField(default=0.0)
    roi_36mo = models.FloatField(default=0.0)
    # Unit economics
    cac_uzs = models.BigIntegerField(default=0)
    ltv_uzs = models.BigIntegerField(default=0)
    ltv_cac_ratio = models.FloatField(default=0.0)
    gross_margin_pct = models.FloatField(default=0.0)
    # Cash flow
    cash_flow_monthly_24 = models.JSONField(default=list)  # 24 values
    # Composite score (0-100)
    viability_score = models.FloatField(default=0.0)
    ai_commentary = models.TextField(blank=True)
    raw_data = models.JSONField(default=dict)
    is_mock = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'D Blok — Moliyaviy maqsadga muvofiqlik'

    def __str__(self):
        return f"Block D: {self.request}"
