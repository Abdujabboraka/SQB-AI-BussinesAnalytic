import json
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from apps.core.models import BusinessAnalysisRequest
from .models import BlockDResult


class BlockDView(LoginRequiredMixin, View):
    template_name = 'blocks/block_d.html'

    def get(self, request, pk):
        analysis = get_object_or_404(BusinessAnalysisRequest, pk=pk, client=request.user)
        block = BlockDResult.objects.filter(request=analysis).first()
        ext = analysis.external_checks or {}
        block_evidence = ext.get("block_evidence", {}).get("D", {})
        ctx = {'analysis': analysis, 'block': block, 'block_evidence': block_evidence}
        if block:
            ctx['mc_distribution'] = json.dumps([int(v) for v in block.mc_profit_distribution])
            ctx['cashflow_labels'] = json.dumps([f"Oy {i+1}" for i in range(24)])
            ctx['cashflow_data'] = json.dumps([int(v) for v in block.cash_flow_monthly_24])
            ctx['comparison_json'] = json.dumps((block.raw_data or {}).get('comparison', []))
            ctx['radial_json'] = json.dumps({
                'bep_score': min(100, max(0, round(100 - (block.breakeven_months / 48) * 100, 1))),
                'roi_score': min(100, max(0, round(block.roi_12mo, 1))),
                'mc_score': round(block.mc_success_probability, 1),
                'viability': round(block.viability_score, 1),
            })
        return render(request, self.template_name, ctx)
