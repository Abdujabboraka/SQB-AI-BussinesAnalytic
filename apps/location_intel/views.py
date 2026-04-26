import json
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from apps.core.models import BusinessAnalysisRequest
from .models import BlockCResult


class BlockCView(LoginRequiredMixin, View):
    template_name = 'blocks/block_c.html'

    def get(self, request, pk):
        analysis = get_object_or_404(BusinessAnalysisRequest, pk=pk, client=request.user)
        block = BlockCResult.objects.filter(request=analysis).first()
        ext = analysis.external_checks or {}
        block_evidence = ext.get("block_evidence", {}).get("C", {})
        ctx = {'analysis': analysis, 'block': block, 'block_evidence': block_evidence}
        if block:
            ctx['competitors_json'] = json.dumps(block.competitors_1km)
            ctx['anchors_json'] = json.dumps(block.anchor_businesses)
            ctx['hourly_labels'] = json.dumps([f"{h}:00" for h in range(24)])
            ctx['hourly_data'] = json.dumps(block.hourly_footfall)
            ctx['daily_labels'] = json.dumps(['Dushanba', 'Seshanba', 'Chorshanba',
                                              'Payshanba', 'Juma', 'Shanba', 'Yakshanba'])
            ctx['daily_data'] = json.dumps(block.daily_footfall)
        return render(request, self.template_name, ctx)
