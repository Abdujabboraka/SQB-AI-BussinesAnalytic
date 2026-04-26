from django.db import models
from apps.core.models import BusinessAnalysisRequest


class BlockCResult(models.Model):
    request = models.OneToOneField(
        BusinessAnalysisRequest, on_delete=models.CASCADE, related_name='block_c'
    )
    location_score = models.FloatField(default=0.0)       # 0 – 100
    # Footfall
    hourly_footfall = models.JSONField(default=list)      # 24 values
    daily_footfall = models.JSONField(default=list)       # 7 values
    # Isochrone demand (estimated people within walk time)
    isochrone_demand_5min = models.IntegerField(default=0)
    isochrone_demand_10min = models.IntegerField(default=0)
    # Anchor businesses
    anchor_businesses = models.JSONField(default=list)    # [{name, type, distance_m}]
    anchor_effect_score = models.FloatField(default=0.0) # 0 – 100
    # Competitors
    competitors_300m = models.JSONField(default=list)
    competitors_1km = models.JSONField(default=list)
    # Text
    ai_commentary = models.TextField(blank=True)
    raw_data = models.JSONField(default=dict)
    is_mock = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'C Blok — Joylashuv razvedkasi'

    def __str__(self):
        return f"Block C: {self.request}"
