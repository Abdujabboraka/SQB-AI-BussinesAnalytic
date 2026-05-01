import json
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from apps.core.models import BusinessAnalysisRequest
from .models import BlockAResult


class BlockAView(LoginRequiredMixin, View):
    template_name = 'blocks/block_a.html'

    def get(self, request, pk):
        analysis = get_object_or_404(BusinessAnalysisRequest, pk=pk, client=request.user)
        block = BlockAResult.objects.filter(request=analysis).first()
        ext = analysis.external_checks or {}
        block_evidence = ext.get("block_evidence", {}).get("A", {})
        ctx = {'analysis': analysis, 'block': block, 'block_evidence': block_evidence}
        if block:
            ctx['funnel_data'] = json.dumps([block.tam_uzs, block.sam_uzs, block.som_uzs])
            ctx['saturation_pct'] = round(block.saturation_index * 100, 1)
            ctx['comparison_json'] = json.dumps((block.raw_data or {}).get('comparison', []))
            ctx['scores_json'] = json.dumps({
                'gap_score': round(block.gap_score, 1),
                'niche_score': round(block.niche_opportunity_score, 1),
                'saturation_inv': round((1 - block.saturation_index) * 100, 1),
            })
        return render(request, self.template_name, ctx)
