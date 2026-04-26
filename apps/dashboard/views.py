import json
import logging
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from io import BytesIO

logger = logging.getLogger(__name__)

from apps.core.models import BusinessAnalysisRequest
from services.scoring_engine import ScoringEngine


class DashboardView(LoginRequiredMixin, View):
    template_name = 'dashboard/dashboard.html'

    def get(self, request, pk):
        is_officer = hasattr(request.user, 'profile') and request.user.profile.is_officer()
        qs = BusinessAnalysisRequest.objects
        analysis = get_object_or_404(qs if is_officer else qs.filter(client=request.user), pk=pk)

        # Gather available block results
        block_a = getattr(analysis, 'block_a', None)
        block_b = getattr(analysis, 'block_b', None)
        block_c = getattr(analysis, 'block_c', None)
        block_d = getattr(analysis, 'block_d', None)
        block_e = getattr(analysis, 'block_e', None)

        # Compute scoring breakdown for display
        block_scores = ScoringEngine.derive_block_scores(block_a, block_b, block_c, block_d, block_e)
        scoring = ScoringEngine().compute_composite(block_scores)

        # Score donut data
        score = analysis.final_score or scoring['composite_score']
        donut_data = json.dumps([round(score, 1), round(100 - score, 1)])

        # Block summary cards data
        block_cards = [
            {
                'letter': 'A', 'label': 'Bozor Tahlili',
                'icon': 'bi-graph-up-arrow', 'color': 'primary',
                'score': round(block_scores.get('A', 0), 1),
                'key_metric': f"Nisha bali: {block_scores.get('A', 0):.0f}/100",
                'url': f'/analysis/{pk}/block-a/',
                'available': block_a is not None,
            },
            {
                'letter': 'B', 'label': 'Talab Prognozi',
                'icon': 'bi-bar-chart-line', 'color': 'info',
                'score': round(block_scores.get('B', 0), 1),
                'key_metric': f"P50 daromad: {_fmt_uzs(block_b.revenue_p50 if block_b else 0)}",
                'url': f'/analysis/{pk}/block-b/',
                'available': block_b is not None,
            },
            {
                'letter': 'C', 'label': 'Joylashuv',
                'icon': 'bi-geo-alt', 'color': 'success',
                'score': round(block_scores.get('C', 0), 1),
                'key_metric': f"Joylashuv bali: {block_scores.get('C', 0):.0f}/100",
                'url': f'/analysis/{pk}/block-c/',
                'available': block_c is not None,
            },
            {
                'letter': 'D', 'label': 'Moliyaviy',
                'icon': 'bi-cash-coin', 'color': 'warning',
                'score': round(block_scores.get('D', 0), 1),
                'key_metric': f"BEP: {block_d.breakeven_months:.1f} oy" if block_d else "—",
                'url': f'/analysis/{pk}/block-d/',
                'available': block_d is not None,
            },
            {
                'letter': 'E', 'label': 'Raqobat & Risk',
                'icon': 'bi-shield-exclamation', 'color': 'danger',
                'score': round(block_scores.get('E', 0), 1),
                'key_metric': f"Risk bali: {block_e.market_risk_score:.0f}/100" if block_e else "—",
                'url': f'/analysis/{pk}/block-e/',
                'available': block_e is not None,
            },
        ]

        is_officer = hasattr(request.user, 'profile') and request.user.profile.is_officer()

        # ── SQB Credit Score ───────────────────────────────────
        from services.scoring_engine import SQBCreditScorer
        sqb_scorer = SQBCreditScorer()

        # Use cached SQB score from analysis record if available, else recompute
        if analysis.sqb_composite_score is not None:
            sqb_result = {
                'composite_score': analysis.sqb_composite_score,
                'verdict': analysis.sqb_recommendation,
                'verdict_color': analysis.sqb_recommendation_color,
                'dsc_ratio': analysis.sqb_dsc_ratio,
                'collateral_coverage': analysis.sqb_collateral_coverage,
                'debt_burden_pct': analysis.sqb_debt_burden_pct,
                'flags': {
                    'dsc_ok': (analysis.sqb_dsc_ratio or 0) >= sqb_scorer.MIN_DSC_RATIO,
                    'collateral_ok': (analysis.sqb_collateral_coverage or 0) >= sqb_scorer.MIN_COLLATERAL_COVERAGE,
                    'debt_burden_ok': (analysis.sqb_debt_burden_pct or 100) <= sqb_scorer.MAX_DEBT_BURDEN_PCT,
                    'own_capital_ok': (float(analysis.own_capital or 0) / float(analysis.investment_amount or 1) * 100) >= sqb_scorer.MIN_OWN_CAPITAL_PCT,
                },
                'breakdown': {},
                'grace_period_months': 6,
                'category': analysis.business_category_type,
            }
        else:
            daily = getattr(analysis, 'expected_daily_customers', 50) or 50
            check = float(getattr(analysis, 'average_check_uzs', 50000) or 50000)
            days  = getattr(analysis, 'working_days_per_week', 7) or 7
            monthly_rev = block_b.revenue_p50 if block_b else daily * check * days * 4.3
            sqb_result = sqb_scorer.compute(analysis, monthly_revenue=monthly_rev)

        # Category-specific detail object
        cat = analysis.business_category_type
        category_detail = None
        try:
            if cat == 'hotel':
                category_detail = analysis.hotel_detail
            elif cat == 'construction':
                category_detail = analysis.construction_detail
            elif cat == 'textile':
                category_detail = analysis.textile_detail
            elif cat == 'trade':
                category_detail = analysis.trade_detail
        except Exception:
            pass

        external_checks = analysis.external_checks or {}
        if not external_checks:
            try:
                from services.web_evidence_service import ExternalEvidenceService

                external_checks = ExternalEvidenceService().build_report(analysis)
                analysis.external_checks = external_checks
                analysis.external_checks_updated_at = timezone.now()
                analysis.save(update_fields=['external_checks', 'external_checks_updated_at'])
            except Exception:
                external_checks = {}

        # ── Benchmarking ──────────────────────────────────────
        revenue_diff_pct = 0
        if block_b and analysis.target_monthly_revenue:
            user_rev = float(analysis.target_monthly_revenue)
            ai_rev = float(block_b.revenue_p50)
            if ai_rev > 0:
                revenue_diff_pct = ((user_rev - ai_rev) / ai_rev) * 100

        # Investment Benchmark (District Average - Mocked for now)
        investment_benchmark = 500_000_000 # Example average
        investment_diff_pct = 0
        if analysis.investment_amount:
            investment_diff_pct = ((float(analysis.investment_amount) - investment_benchmark) / investment_benchmark) * 100

        ctx = {
            'analysis': analysis,
            'block_a': block_a,
            'block_b': block_b,
            'block_c': block_c,
            'block_d': block_d,
            'block_e': block_e,
            'scoring': scoring,
            'final_score': score,
            'donut_data': donut_data,
            'block_cards': block_cards,
            'is_officer': is_officer,
            'sqb': sqb_result,
            'category_detail': category_detail,
            'competitors_json': json.dumps(
                (block_e.competitors_1km if block_e else []) or (block_c.competitors_1km if block_c else [])
            ),
            'external_checks': external_checks,
            'benchmarks': {
                'revenue_diff_pct': round(revenue_diff_pct, 1),
                'investment_diff_pct': round(investment_diff_pct, 1),
                'ai_revenue_p50': block_b.revenue_p50 if block_b else 0,
            }
        }
        return render(request, self.template_name, ctx)


class PDFExportView(LoginRequiredMixin, View):
    def _build_reportlab_pdf(self, analysis, block_a, block_b, block_c, block_d, block_e, sqb_result):
        """
        Windows-friendly PDF generator (no GTK/system dependencies).
        """
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        y = height - 20 * mm

        def line(text, size=10, bold=False, step=6):
            nonlocal y
            c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
            c.drawString(18 * mm, y, str(text))
            y -= step * mm

        line("SQB Bank - BiznesAI Kredit Tahlil Hisoboti", size=14, bold=True, step=8)
        line(f"Tahlil ID: {analysis.pk}", bold=True)
        line(f"Biznes turi: {analysis.business_type}")
        line(f"Tuman: {analysis.district}")
        line(f"Sana: {analysis.created_at.strftime('%d.%m.%Y %H:%M')}")
        line(f"Yakuniy tavsiya: {analysis.get_recommendation_display_uz()}")
        line(f"Yakuniy ball: {analysis.final_score or 0}/100")

        y -= 2 * mm
        line("Moliyaviy ko'rsatkichlar", bold=True)
        line(f"Investitsiya: {analysis.investment_amount:,.0f} so'm")
        line(f"Kredit: {analysis.loan_amount:,.0f} so'm")
        line(f"O'z kapitali: {analysis.own_capital:,.0f} so'm")
        line(f"Oylik doimiy xarajat: {analysis.monthly_fixed_costs:,.0f} so'm")

        y -= 2 * mm
        line("Blok natijalari", bold=True)
        if block_a:
            line(f"A (Bozor): {block_a.niche_opportunity_score:.1f}/100")
        if block_b:
            line(f"B (Talab): {block_b.demand_score:.1f}/100  |  P50: {block_b.revenue_p50:,.0f} so'm")
        if block_c:
            line(f"C (Joylashuv): {block_c.location_score:.1f}/100")
        if block_d:
            line(f"D (Moliyaviy): {block_d.viability_score:.1f}/100  |  ROI12: {block_d.roi_12mo:.1f}%")
        if block_e:
            line(f"E (Risk): {block_e.market_risk_score:.1f}/100")

        y -= 2 * mm
        line("SQB kredit bahosi", bold=True)
        line(f"Kompozit: {sqb_result.get('composite_score', 0):.1f}/100")
        line(f"DSC: {sqb_result.get('dsc_ratio', 0):.2f}")
        line(f"Garov qoplami: {sqb_result.get('collateral_coverage', 0):.2f}x")
        line(f"Qarz yuki: {sqb_result.get('debt_burden_pct', 0):.1f}%")
        line(f"Xulosa: {sqb_result.get('verdict', '-')}")

        if analysis.final_commentary:
            y -= 2 * mm
            line("AI xulosa (qisqa):", bold=True)
            commentary = analysis.final_commentary.replace('\n', ' ')
            for i in range(0, min(len(commentary), 900), 110):
                line(commentary[i:i + 110], size=9, step=5)

        c.showPage()
        c.save()
        pdf = buffer.getvalue()
        buffer.close()
        return pdf

    def get(self, request, pk):
        is_officer = hasattr(request.user, 'profile') and request.user.profile.is_officer()
        qs = BusinessAnalysisRequest.objects
        analysis = get_object_or_404(qs if is_officer else qs.filter(client=request.user), pk=pk)
        block_a = getattr(analysis, 'block_a', None)
        block_b = getattr(analysis, 'block_b', None)
        block_c = getattr(analysis, 'block_c', None)
        block_d = getattr(analysis, 'block_d', None)
        block_e = getattr(analysis, 'block_e', None)
        external_checks = analysis.external_checks or {}
        if not external_checks:
            try:
                from services.web_evidence_service import ExternalEvidenceService

                external_checks = ExternalEvidenceService().build_report(analysis)
                analysis.external_checks = external_checks
                analysis.external_checks_updated_at = timezone.now()
                analysis.save(update_fields=['external_checks', 'external_checks_updated_at'])
            except Exception:
                external_checks = {}

        # Build SQB score data for the PDF template
        from services.scoring_engine import SQBCreditScorer
        sqb_scorer = SQBCreditScorer()
        if analysis.sqb_composite_score is not None:
            sqb_result = {
                'composite_score': analysis.sqb_composite_score,
                'verdict': analysis.sqb_recommendation,
                'verdict_color': analysis.sqb_recommendation_color,
                'dsc_ratio': analysis.sqb_dsc_ratio or 0,
                'collateral_coverage': analysis.sqb_collateral_coverage or 0,
                'debt_burden_pct': analysis.sqb_debt_burden_pct or 0,
                'flags': {
                    'dsc_ok': (analysis.sqb_dsc_ratio or 0) >= sqb_scorer.MIN_DSC_RATIO,
                    'collateral_ok': (analysis.sqb_collateral_coverage or 0) >= sqb_scorer.MIN_COLLATERAL_COVERAGE,
                    'debt_burden_ok': (analysis.sqb_debt_burden_pct or 100) <= sqb_scorer.MAX_DEBT_BURDEN_PCT,
                    'own_capital_ok': (float(analysis.own_capital or 0) / float(analysis.investment_amount or 1) * 100) >= sqb_scorer.MIN_OWN_CAPITAL_PCT,
                },
                'grace_period_months': 6,
            }
        else:
            daily = getattr(analysis, 'expected_daily_customers', 50) or 50
            check = float(getattr(analysis, 'average_check_uzs', 50000) or 50000)
            days  = getattr(analysis, 'working_days_per_week', 7) or 7
            rev   = block_b.revenue_p50 if block_b else daily * check * days * 4.3
            sqb_result = sqb_scorer.compute(analysis, monthly_revenue=rev)

        ctx = {
            'analysis': analysis,
            'block_a': block_a, 'block_b': block_b,
            'block_c': block_c, 'block_d': block_d, 'block_e': block_e,
            'external_checks': external_checks,
            'sqb': sqb_result,
        }
        fname = f"SQB_BiznesAI_{analysis.business_type.replace(' ', '_')}_{pk}.pdf"

        # Try WeasyPrint first (best HTML fidelity), fallback to ReportLab on Windows/dev.
        try:
            from weasyprint import HTML
            from django.template.loader import render_to_string
            html_string = render_to_string('reports/report.html', ctx, request=request)
            html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
            pdf = html.write_pdf()
        except Exception as exc:
            logger.warning("WeasyPrint unavailable/failed, fallback to ReportLab: %s", exc)
            try:
                pdf = self._build_reportlab_pdf(analysis, block_a, block_b, block_c, block_d, block_e, sqb_result)
            except Exception as rb_exc:
                logger.error("ReportLab PDF generation failed: %s", rb_exc)
                return HttpResponse(f"PDF yaratishda xato: {rb_exc}", status=500)

        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response


def _fmt_uzs(value: int) -> str:
    if value >= 1_000_000_000:
        return f"{value/1_000_000_000:.1f} mlrd"
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f} mln"
    return f"{value:,}"
