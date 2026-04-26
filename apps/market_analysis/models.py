from django.db import models
from apps.core.models import BusinessAnalysisRequest


class BlockAResult(models.Model):
    request = models.OneToOneField(
        BusinessAnalysisRequest, on_delete=models.CASCADE, related_name='block_a'
    )
    # TAM/SAM/SOM
    tam_uzs = models.BigIntegerField(default=0, verbose_name='TAM (so\'m)')
    sam_uzs = models.BigIntegerField(default=0, verbose_name='SAM (so\'m)')
    som_uzs = models.BigIntegerField(default=0, verbose_name='SOM (so\'m)')
    # Scores
    saturation_index = models.FloatField(default=0.0)  # 0.0 – 1.0
    gap_score = models.FloatField(default=0.0)          # 0 – 100
    niche_opportunity_score = models.FloatField(default=0.0)  # 0 – 100
    # Gemini text
    ai_commentary = models.TextField(blank=True)
    # Raw payload
    raw_data = models.JSONField(default=dict)
    is_mock = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'A Blok — Bozor tahlili'

    def __str__(self):
        return f"Block A: {self.request}"
