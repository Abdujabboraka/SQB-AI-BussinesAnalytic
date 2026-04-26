import json
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from apps.core.models import BusinessAnalysisRequest
from .models import BlockBResult


class BlockBView(LoginRequiredMixin, View):
    template_name = 'blocks/block_b.html'

    def get(self, request, pk):
        analysis = get_object_or_404(BusinessAnalysisRequest, pk=pk, client=request.user)
        block = BlockBResult.objects.filter(request=analysis).first()
        ext = analysis.external_checks or {}
        block_evidence = ext.get("block_evidence", {}).get("B", {})
        ctx = {'analysis': analysis, 'block': block, 'block_evidence': block_evidence}
        if block:
            forecast = block.monthly_forecast_12
            labels = [f"Oy {i+1}" for i in range(len(forecast))]
            ctx['forecast_labels'] = json.dumps(labels)
            ctx['forecast_p50'] = json.dumps([int(v) for v in forecast])
            ctx['forecast_low'] = json.dumps([int(v) for v in block.confidence_low_12])
            ctx['forecast_high'] = json.dumps([int(v) for v in block.confidence_high_12])
            ctx['weekly_labels'] = json.dumps(['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sha', 'Ya'])
            ctx['weekly_data'] = json.dumps(block.seasonality_weekly)
        return render(request, self.template_name, ctx)
