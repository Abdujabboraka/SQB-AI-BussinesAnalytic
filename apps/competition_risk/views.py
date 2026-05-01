import json
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from apps.core.models import BusinessAnalysisRequest
from .models import BlockEResult


class BlockEView(LoginRequiredMixin, View):
    template_name = 'blocks/block_e.html'

    def get(self, request, pk):
        analysis = get_object_or_404(BusinessAnalysisRequest, pk=pk, client=request.user)
        block = BlockEResult.objects.filter(request=analysis).first()
        ext = analysis.external_checks or {}
        block_evidence = ext.get("block_evidence", {}).get("E", {})
        ctx = {'analysis': analysis, 'block': block, 'block_evidence': block_evidence}
        if block:
            all_comps = block.competitors_1km or []
            ctx['competitors_json'] = json.dumps(all_comps)
            names = [c.get('name', '?')[:20] for c in all_comps[:10]]
            probs = [round(c.get('closure_probability', 0) * 100, 1) for c in all_comps[:10]]
            ctx['comp_names'] = json.dumps(names)
            ctx['comp_closure_probs'] = json.dumps(probs)
            ctx['entry_barriers'] = block.entry_barriers
            ctx['comparison_json'] = json.dumps((block.raw_data or {}).get('comparison', []))
            # Scatter data: distance vs closure_probability per competitor
            scatter = [
                {'x': round(c.get('distance_m', 0)), 'y': round(c.get('closure_probability', 0) * 100, 1),
                 'name': c.get('name', '?')[:16]}
                for c in all_comps if c.get('distance_m') is not None
            ]
            ctx['scatter_json'] = json.dumps(scatter)
        return render(request, self.template_name, ctx)
