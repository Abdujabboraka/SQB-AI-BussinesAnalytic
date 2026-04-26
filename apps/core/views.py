import json
import logging
import math
import requests
from django.db import OperationalError
import threading
from django.conf import settings
from django.views import View
from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages

from .models import BusinessAnalysisRequest, UserProfile, Zalog
from .forms import (
    Step1Form, Step2Form, Step3Form, Step4Form, UserRegisterForm,
    HotelDetailForm, ConstructionDetailForm, TextileDetailForm, TradeDetailForm, ServiceDetailForm,
)

logger = logging.getLogger(__name__)


class HomeView(LoginRequiredMixin, ListView):
    template_name = 'core/home.html'
    context_object_name = 'analyses'
    paginate_by = 10

    def get_queryset(self):
        return BusinessAnalysisRequest.objects.filter(
            client=self.request.user
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        ctx['total_count'] = qs.count()
        ctx['done_count'] = qs.filter(status='done').count()
        ctx['ha_count'] = qs.filter(final_recommendation='YES').count()
        ctx['yoq_count'] = qs.filter(final_recommendation='NO').count()
        ctx['is_officer'] = hasattr(self.request.user, 'profile') and self.request.user.profile.is_officer()
        return ctx


class AnalysisCreateView(LoginRequiredMixin, View):
    template_name = 'core/analysis_form.html'

    STEPS = [
        (1, 'Biznes', 'bi-pencil-square'),
        (2, 'Talab', 'bi-bar-chart'),
        (3, 'Joylashuv', 'bi-geo-alt'),
        (4, 'Moliya', 'bi-cash-coin'),
    ]

    CATEGORY_DETAIL_FORMS = {
        'hotel':        HotelDetailForm,
        'construction': ConstructionDetailForm,
        'textile':      TextileDetailForm,
        'trade':        TradeDetailForm,
        'services':     ServiceDetailForm,
        'tourism':      HotelDetailForm,  # Re-use hotel form for tourism
    }

    def _get_forms(self, data=None):
        """Return (forms_dict, context_dict). forms_dict contains only Form objects."""
        f1 = Step1Form(data, prefix='s1')
        f2 = Step2Form(data, prefix='s2')
        f3 = Step3Form(data, prefix='s3')
        f4 = Step4Form(data, prefix='s4')
        forms_only = {'form1': f1, 'form2': f2, 'form3': f3, 'form4': f4}
        ctx = {**forms_only, 'steps': self.STEPS}
        return forms_only, ctx

    def _get_category_form(self, category, data=None):
        """Return the category-specific detail form if applicable."""
        form_cls = self.CATEGORY_DETAIL_FORMS.get(category)
        if form_cls:
            return form_cls(data, prefix='cat')
        return None

    def get(self, request):
        # Pre-fill from a previously saved analysis
        prefill_data = None
        edit_from = request.GET.get('edit_from')
        if edit_from:
            try:
                src = BusinessAnalysisRequest.objects.get(pk=edit_from, client=request.user)
                prefill_data = src.form_data_json or None
            except BusinessAnalysisRequest.DoesNotExist:
                pass

        _, ctx = self._get_forms(prefill_data)
        ctx['category_forms'] = {
            k: cls(prefill_data, prefix='cat') if prefill_data else cls(prefix='cat')
            for k, cls in self.CATEGORY_DETAIL_FORMS.items()
        }
        ctx['prefill_data'] = json.dumps(prefill_data) if prefill_data else 'null'
        return render(request, self.template_name, ctx)

    def post(self, request):
        forms_only, ctx = self._get_forms(request.POST)
        all_valid = all(f.is_valid() for f in forms_only.values())

        # Determine category early (needed for detail form)
        # 'tourism' shares the hotel detail form
        category = request.POST.get('s1-business_category_type', 'hotel')
        detail_category = 'hotel' if category == 'tourism' else category
        cat_form = self._get_category_form(detail_category, request.POST)
        cat_form_valid = (cat_form is None) or cat_form.is_valid()

        ctx['category_forms'] = {
            k: cls(request.POST if k == detail_category else None, prefix='cat')
            for k, cls in self.CATEGORY_DETAIL_FORMS.items()
        }

        if all_valid and cat_form_valid:
            try:
                # ── Build core analysis ────────────────────────────
                analysis = BusinessAnalysisRequest(client=request.user)
                # Save raw form data so failed analyses can be retried/edited
                import json as _json
                analysis.form_data_json = {k: v if len(v) > 1 else v[0] for k, v in request.POST.lists()
                                           if k not in ('csrfmiddlewaretoken',)}
                for form in forms_only.values():
                    for field, value in form.cleaned_data.items():
                        if hasattr(analysis, field):
                            setattr(analysis, field, value)

                extra_monthly_costs = sum(
                    float(forms_only['form4'].cleaned_data.get(field) or 0)
                    for field in (
                        'monthly_marketing_uzs',
                        'monthly_logistics_uzs',
                        'monthly_maintenance_uzs',
                        'monthly_software_uzs',
                        'monthly_security_uzs',
                        'monthly_other_costs_uzs',
                    )
                )
                # Dynamic custom cost rows from the "+ Qo'shish" button
                try:
                    custom_costs_raw = forms_only['form4'].cleaned_data.get('extra_costs_json') or '[]'
                    custom_costs = _json.loads(custom_costs_raw) if isinstance(custom_costs_raw, str) else []
                    custom_total = sum(float(row.get('amount', 0)) for row in custom_costs if isinstance(row, dict))
                    extra_monthly_costs += custom_total
                    if custom_costs:
                        analysis.extra_costs_json = custom_costs
                except Exception:
                    pass
                analysis.own_capital = max(
                    float(analysis.investment_amount or 0) - float(analysis.loan_amount or 0),
                    0,
                )
                analysis.monthly_fixed_costs = analysis.computed_monthly_fixed_costs + extra_monthly_costs
                analysis.variable_cost_pct = analysis.cogs_percentage
                analysis.save()

                # ── Save category detail model ─────────────────────
                if cat_form and cat_form.is_valid():
                    self._save_category_detail(analysis, detail_category, cat_form.cleaned_data)

                # ── Run SQB Credit Scorer immediately ─────────────
                try:
                    from services.scoring_engine import SQBCreditScorer
                    scorer = SQBCreditScorer()
                    monthly_rev = float(analysis.target_monthly_revenue or 0)
                    if monthly_rev <= 0:
                        daily = getattr(analysis, 'expected_daily_customers', 50) or 50
                        check = float(getattr(analysis, 'average_check_uzs', 50000) or 50000)
                        days  = getattr(analysis, 'working_days_per_week', 7) or 7
                        monthly_rev = daily * check * days * 4.3
                    
                    sqb = scorer.compute(analysis, monthly_revenue=monthly_rev)
                    analysis.sqb_composite_score = sqb['composite_score']
                    analysis.sqb_recommendation = sqb['verdict']
                    analysis.sqb_recommendation_color = sqb['verdict_color']
                    analysis.sqb_dsc_ratio = sqb['dsc_ratio']
                    analysis.sqb_collateral_coverage = sqb['collateral_coverage']
                    analysis.sqb_debt_burden_pct = sqb['debt_burden_pct']
                    analysis.save(update_fields=[
                        'sqb_composite_score', 'sqb_recommendation', 'sqb_recommendation_color',
                        'sqb_dsc_ratio', 'sqb_collateral_coverage', 'sqb_debt_burden_pct',
                    ])
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"SQB scoring failed: {e}")

                # ── Launch Background Tahlil ───────────────────────
                try:
                    from apps.core.tasks import run_full_analysis
                    if getattr(settings, 'USE_CELERY', False):
                        task = run_full_analysis.delay(analysis.pk)
                        analysis.celery_task_id = task.id if hasattr(task, 'id') else ''
                        analysis.save(update_fields=['celery_task_id'])
                    else:
                        # Threaded execution for instant response without Celery
                        thread = threading.Thread(target=run_full_analysis, args=(None, analysis.pk))
                        thread.daemon = True
                        thread.start()
                except Exception as e:
                    logging.getLogger(__name__).error(f"Dispatch failed: {e}")
                    analysis.status = 'failed'
                    analysis.warning_message = str(e)
                    analysis.save(update_fields=['status', 'warning_message'])

                messages.success(request, "Tahlil jarayoni boshlandi. Iltimos, natijalarni kuting!")
                return redirect('analysis_status_page', pk=analysis.pk)
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception("Error creating analysis request")
                messages.error(request, f"Tizim xatosi: {str(e)}")
                return render(request, self.template_name, ctx)

        # Re-render with validation errors
        return render(request, self.template_name, ctx)

    def _save_category_detail(self, analysis, category, data):
        """Create/update the appropriate category detail model."""
        from apps.category_analysis.models import (
            HotelDetail, ConstructionDetail, TextileDetail, TradeDetail
        )
        if category == 'hotel':
            HotelDetail.objects.update_or_create(
                request=analysis,
                defaults={
                    'hotel_name': data.get('hotel_name', ''),
                    'hotel_category': data.get('hotel_category', '3_star'),
                    'total_rooms': data.get('total_rooms', 20),
                    'city': data.get('city', 'tashkent'),
                    'room_rate_low_usd': data.get('room_rate_low_usd', 40),
                    'room_rate_high_usd': data.get('room_rate_high_usd', 80),
                    'target_occupancy_pct': data.get('target_occupancy_pct', 65.0),
                    'applying_for_subsidy': data.get('applying_for_subsidy', False),
                    'franchise_agreement': data.get('franchise_agreement', False),
                    'booking_profile': data.get('booking_profile', 'no'),
                    'advance_booking_pct': data.get('advance_booking_pct', 30),
                    'collateral_type': data.get('collateral_type', 'property'),
                    'booking_platforms': {
                        'tariff_system': data.get('tariff_system', 'seasonal'),
                        'extra_tariff_label': data.get('extra_tariff_label', ''),
                        'extra_tariff_value_usd': float(data.get('extra_tariff_value_usd') or 0),
                    },
                }
            )
        elif category == 'tourism':
             # Tourism uses same fields as hotel
             HotelDetail.objects.update_or_create(
                request=analysis,
                defaults={
                    'hotel_name': data.get('hotel_name', 'Tourism Project'),
                    'hotel_category': data.get('hotel_category', 'boutique'),
                    'total_rooms': data.get('total_rooms', 10),
                    'city': data.get('city', 'tashkent'),
                    'booking_profile': data.get('booking_profile', 'no'),
                    'advance_booking_pct': data.get('advance_booking_pct', 30),
                    'collateral_type': data.get('collateral_type', 'property'),
                }
             )
        elif category == 'construction':
            ConstructionDetail.objects.update_or_create(
                request=analysis,
                defaults={
                    'has_license': data.get('has_license', False),
                    'license_category': data.get('license_category', 'none'),
                    'months_to_get_license': data.get('months_to_get_license', 3),
                    'months_to_first_income': data.get('months_to_first_income', 6),
                    'expected_first_contract_size_uzs': data.get('expected_first_contract_size_uzs', 50_000_000),
                    'average_project_duration_months': data.get('average_project_duration_months', 6),
                    'num_engineers': data.get('num_engineers', 2),
                    'num_workers': data.get('num_workers', 10),
                    'average_margin_pct': data.get('average_margin_pct', 18.0),
                    'current_contracts': data.get('current_contracts', ''),
                    'subcontractor_network': data.get('subcontractor_network', False),
                    'project_type': data.get('project_type', 'private'),
                    'equipment_pct': data.get('equipment_pct', 50),
                    'license_valid': data.get('license_valid', True),
                }
            )
        elif category == 'textile':
            TextileDetail.objects.update_or_create(
                request=analysis,
                defaults={
                    'production_capacity_monthly': data.get('production_capacity_monthly', 1000),
                    'unit_of_measure': data.get('unit_of_measure', 'meters'),
                    'raw_material_monthly_uzs': data.get('raw_material_monthly_uzs', 0),
                    'export_experience': data.get('export_experience', False),
                    'existing_buyers': data.get('existing_buyers', ''),
                    'months_to_get_cert': data.get('months_to_get_cert', 6),
                    'machinery_age_years': data.get('machinery_age_years', 5),
                    'num_workers_skilled': data.get('num_workers_skilled', 10),
                    'electricity_monthly': data.get('electricity_monthly', 2_000_000),
                    'export_pct': data.get('export_pct', 30),
                    'market_type': data.get('market_type', 'domestic'),
                    'cert_type': data.get('cert_type', 'gost'),
                    'factory_sqm': data.get('factory_sqm', 500),
                }
            )
        elif category == 'trade':
            TradeDetail.objects.update_or_create(
                request=analysis,
                defaults={
                    'trade_type': data.get('trade_type', 'grocery'),
                    'store_format': data.get('store_format', 'street_shop'),
                    'foot_traffic': data.get('foot_traffic', 'medium'),
                    'avg_monthly_stock_uzs': data.get('avg_monthly_stock_uzs', 10_000_000),
                    'avg_markup_pct': data.get('avg_markup_pct', 25.0),
                    'inventory_turnover_days': data.get('inventory_turnover_days', 30),
                    'supplier_credit_days': data.get('supplier_credit_days', 14),
                    'direct_competitors_300m': data.get('direct_competitors_300m', 2),
                    'price_strategy': data.get('price_strategy', 'mid'),
                    'suppliers_count': data.get('suppliers_count', 3),
                    'credit_line_needed': data.get('credit_line_needed', 0),
                    'stock_turnover': data.get('stock_turnover', 30),
                }
            )
        elif category == 'services':
            from apps.category_analysis.models import ServiceDetail
            ServiceDetail.objects.update_or_create(
                request=analysis,
                defaults={
                    'provider_type': data.get('provider_type', 'individual'),
                    'equipment_uzs': data.get('equipment_uzs', 0),
                    'repeat_pct': data.get('repeat_pct', 40),
                    'service_avg_price': data.get('service_avg_price', 150000),
                }
            )
class AnalysisStatusPageView(LoginRequiredMixin, View):
    """Polling page — shown while Celery tasks run."""
    template_name = 'core/analysis_status.html'

    BLOCK_ITEMS = [('A','Bozor'),('B','Talab'),('C','Joylashuv'),('D','Moliyaviy'),('E','Raqobat')]

    def get(self, request, pk):
        is_officer = hasattr(request.user, 'profile') and request.user.profile.is_officer()
        qs = BusinessAnalysisRequest.objects
        analysis = get_object_or_404(qs if is_officer else qs.filter(client=request.user), pk=pk)
        if analysis.status == 'done':
            return redirect('dashboard', pk=pk)
        return render(request, self.template_name, {
            'analysis': analysis,
            'block_items': self.BLOCK_ITEMS,
        })


class AnalysisStatusAPIView(LoginRequiredMixin, View):
    """AJAX endpoint for polling progress."""
    def get(self, request, pk):
        analysis = get_object_or_404(BusinessAnalysisRequest, pk=pk, client=request.user)
        data = {
            'status': analysis.status,
            'progress_pct': analysis.progress_pct,
            'completed_blocks': analysis.completed_blocks,
            'warning_flag': analysis.warning_flag,
            'redirect_url': f'/analysis/{pk}/dashboard/' if analysis.status == 'done' else None,
        }
        return JsonResponse(data)


class AnalysisNotificationsAPIView(LoginRequiredMixin, View):
    """
    Polling endpoint for Home page toast notifications.
    Returns completed analyses that were not yet notified, then marks them as notified.
    """
    def get(self, request):
        analyses = list(
            BusinessAnalysisRequest.objects.filter(
                client=request.user,
                status='done',
                is_notified=False,
            ).order_by('-updated_at')[:5]
        )

        items = [
            {
                'id': a.pk,
                'business_type': a.business_type,
                'final_recommendation': a.final_recommendation,
                'final_score': a.final_score,
                'dashboard_url': reverse('dashboard', kwargs={'pk': a.pk}),
                'pdf_url': reverse('pdf_export', kwargs={'pk': a.pk}),
            }
            for a in analyses
        ]

        if analyses:
            BusinessAnalysisRequest.objects.filter(
                pk__in=[a.pk for a in analyses]
            ).update(is_notified=True)

        return JsonResponse({'notifications': items})


class LocationLookupAPIView(LoginRequiredMixin, View):
    """Reverse-geocode the selected map point and return nearby competitors."""
    DISTRICT_ALIASES = {
        'yunusobod': 'Yunusobod',
        'chilonzor': 'Chilonzor',
        'mirzo ulug': 'Mirzo Ulugbek',
        'shayxontohur': 'Shayxontohur',
        'olmazor': 'Olmazor',
        'mirobod': 'Mirobod',
        'yakkasaroy': 'Yakkasaroy',
        'bektemir': 'Bektemir',
        'sergeli': 'Sergeli',
        'uchtepa': 'Uchtepa',
        'yashnobod': 'Yashnobod',
        'zangiota': 'Zangiota',
    }
    OVERPASS_URL = 'https://overpass-api.de/api/interpreter'
    OSRM_ROUTE_URL = 'https://router.project-osrm.org/route/v1/driving'

    @staticmethod
    def _haversine_km(lat1, lon1, lat2, lon2):
        radius_km = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)
        a = (math.sin(d_phi / 2) ** 2) + math.cos(phi1) * math.cos(phi2) * (math.sin(d_lambda / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(1e-12, 1 - a)))
        return radius_km * c

    def _route_distance_km(self, src_lat, src_lng, dst_lat, dst_lng):
        try:
            resp = requests.get(
                f"{self.OSRM_ROUTE_URL}/{src_lng},{src_lat};{dst_lng},{dst_lat}",
                params={'overview': 'false', 'alternatives': 'false', 'steps': 'false'},
                timeout=10,
            )
            if resp.ok:
                payload = resp.json()
                routes = payload.get('routes') or []
                if routes:
                    return round(float(routes[0].get('distance', 0)) / 1000, 2), 'osrm'
        except Exception:
            pass
        return round(self._haversine_km(src_lat, src_lng, dst_lat, dst_lng), 2), 'haversine'

    def _query_nearest_place(self, lat, lng, query_body):
        try:
            resp = requests.post(self.OVERPASS_URL, data={'data': query_body}, timeout=14)
            if not resp.ok:
                return None
            elements = resp.json().get('elements') or []
            nearest = None
            nearest_distance = 10**9
            for el in elements:
                p_lat = el.get('lat') or (el.get('center') or {}).get('lat')
                p_lng = el.get('lon') or (el.get('center') or {}).get('lon')
                if p_lat is None or p_lng is None:
                    continue
                dist_km = self._haversine_km(lat, lng, p_lat, p_lng)
                if dist_km < nearest_distance:
                    tags = el.get('tags') or {}
                    nearest = {
                        'name': tags.get('name') or "Noma'lum obyekt",
                        'lat': float(p_lat),
                        'lng': float(p_lng),
                        'distance_km': round(dist_km, 2),
                    }
                    nearest_distance = dist_km
            return nearest
        except Exception as exc:
            logger.warning("Overpass place lookup failed: %s", exc)
            return None

    def _build_hotel_autofill(self, lat, lng):
        airport_query = f"""
[out:json][timeout:12];
(
  node["aeroway"="aerodrome"](around:80000,{lat},{lng});
  way["aeroway"="aerodrome"](around:80000,{lat},{lng});
  node["amenity"="airport"](around:80000,{lat},{lng});
  way["amenity"="airport"](around:80000,{lat},{lng});
);
out center;
"""
        attraction_query = f"""
[out:json][timeout:12];
(
  node["tourism"~"attraction|museum|viewpoint|theme_park|gallery"](around:12000,{lat},{lng});
  way["tourism"~"attraction|museum|viewpoint|theme_park|gallery"](around:12000,{lat},{lng});
);
out center;
"""
        airport = self._query_nearest_place(lat, lng, airport_query)
        attraction = self._query_nearest_place(lat, lng, attraction_query)

        route_sources = []
        airport_km = None
        attraction_km = None

        if airport:
            airport_km, src = self._route_distance_km(lat, lng, airport['lat'], airport['lng'])
            route_sources.append(src)
        if attraction:
            attraction_km, src = self._route_distance_km(lat, lng, attraction['lat'], attraction['lng'])
            route_sources.append(src)

        return {
            'airport_name': (airport or {}).get('name', ''),
            'distance_to_airport_km': airport_km,
            'nearest_attraction_name': (attraction or {}).get('name', ''),
            'distance_to_top_attraction_km': attraction_km,
            'route_source': route_sources[0] if route_sources else 'none',
        }

    def get(self, request):
        try:
            lat = float(request.GET.get('lat'))
            lng = float(request.GET.get('lng'))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'lat/lng required'}, status=400)

        mcc_code = request.GET.get('mcc_code') or '5999'
        result = {
            'district': '',
            'address': '',
            'landmarks': [],
            'competitors': [],
            'source': 'openstreetmap',
            'hotel_autofill': {},
        }

        try:
            resp = requests.get(
                'https://nominatim.openstreetmap.org/reverse',
                params={'format': 'jsonv2', 'lat': lat, 'lon': lng, 'accept-language': 'uz,en,ru'},
                headers={'User-Agent': 'BiznesAI SQB Hackathon'},
                timeout=8,
            )
            if resp.ok:
                payload = resp.json()
                address = payload.get('address', {})
                display_name = payload.get('display_name', '')
                district_text = ' '.join(str(address.get(k, '')) for k in ('suburb', 'city_district', 'county', 'city'))
                lower = district_text.lower()
                for token, district in self.DISTRICT_ALIASES.items():
                    if token in lower:
                        result['district'] = district
                        break
                result['address'] = display_name[:255]
        except Exception as exc:
            logger.warning("Reverse geocoding failed: %s", exc)

        try:
            from services.mcc_data_service import MCCDataService
            svc = MCCDataService()
            competitors = svc.get_competitors_from_osm(lat, lng, mcc_code, radius_m=1000)[:8]
            result['competitors'] = competitors
            result['landmarks'] = [
                f"{c.get('name') or 'Noma lum'} ({c.get('distance_m')}m)"
                for c in competitors[:5]
            ]
        except Exception as exc:
            logger.warning("Competitor lookup failed: %s", exc)

        if mcc_code == '7011':
            try:
                hotel_data = self._build_hotel_autofill(lat, lng)
                result['hotel_autofill'] = hotel_data
                attraction_name = (hotel_data or {}).get('nearest_attraction_name')
                if attraction_name and attraction_name not in result['landmarks']:
                    result['landmarks'].insert(0, attraction_name)
            except Exception as exc:
                logger.warning("Hotel autofill lookup failed: %s", exc)

        return JsonResponse(result)


class AIHealthAPIView(LoginRequiredMixin, View):
    """
    Real-time AI service connectivity check.
    Makes lightweight probe calls to each configured provider to detect quota/rate-limit errors.
    """
    def get(self, request):
        import requests as http_requests
        from django.conf import settings

        providers = {}

        # ── Gemini ──────────────────────────────────────────────
        gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
        if gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                models_list = list(genai.list_models())
                model_name = next(
                    (m.name.split('/')[-1] for m in models_list
                     if hasattr(m, 'supported_generation_methods')
                     and 'generateContent' in (m.supported_generation_methods or [])),
                    'gemini-2.0-flash',
                )
                providers['gemini'] = {
                    'status': 'ok', 'model': model_name,
                    'label': f'Gemini ({model_name})',
                }
            except Exception as exc:
                err = str(exc).lower()
                if 'quota' in err or '429' in err or 'rate' in err or 'limit' in err:
                    providers['gemini'] = {
                        'status': 'quota_exceeded',
                        'label': 'Gemini — limit tugagan ⚠️',
                        'error': str(exc)[:120],
                    }
                elif 'api_key' in err or 'invalid' in err or '400' in err:
                    providers['gemini'] = {
                        'status': 'invalid_key',
                        'label': 'Gemini — kalit noto\'g\'ri ❌',
                        'error': str(exc)[:120],
                    }
                else:
                    providers['gemini'] = {
                        'status': 'error',
                        'label': 'Gemini — xato ❌',
                        'error': str(exc)[:120],
                    }
        else:
            providers['gemini'] = {'status': 'not_configured', 'label': 'Gemini — sozlanmagan'}

        # ── OpenAI ───────────────────────────────────────────────
        openai_key = getattr(settings, 'OPENAI_API_KEY', '')
        if openai_key:
            try:
                resp = http_requests.get(
                    'https://api.openai.com/v1/models',
                    headers={'Authorization': f'Bearer {openai_key}'},
                    timeout=5,
                )
                if resp.status_code == 200:
                    providers['openai'] = {'status': 'ok', 'label': 'OpenAI GPT — tayyor ✅'}
                elif resp.status_code == 429:
                    providers['openai'] = {'status': 'quota_exceeded', 'label': 'OpenAI — limit tugagan ⚠️'}
                else:
                    providers['openai'] = {
                        'status': 'error',
                        'label': f'OpenAI — xato ({resp.status_code}) ❌',
                    }
            except Exception as exc:
                providers['openai'] = {'status': 'error', 'label': 'OpenAI — ulanish xatosi ❌', 'error': str(exc)[:80]}
        else:
            providers['openai'] = {'status': 'not_configured', 'label': 'OpenAI — sozlanmagan'}

        # ── Anthropic ────────────────────────────────────────────
        anthropic_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
        if anthropic_key:
            try:
                resp = http_requests.get(
                    'https://api.anthropic.com/v1/models',
                    headers={
                        'x-api-key': anthropic_key,
                        'anthropic-version': '2023-06-01',
                    },
                    timeout=5,
                )
                if resp.status_code == 200:
                    providers['anthropic'] = {'status': 'ok', 'label': 'Claude (Anthropic) — tayyor ✅'}
                elif resp.status_code == 429:
                    providers['anthropic'] = {'status': 'quota_exceeded', 'label': 'Claude — limit tugagan ⚠️'}
                else:
                    providers['anthropic'] = {
                        'status': 'error',
                        'label': f'Claude — xato ({resp.status_code}) ❌',
                    }
            except Exception as exc:
                providers['anthropic'] = {'status': 'error', 'label': 'Claude — ulanish xatosi ❌', 'error': str(exc)[:80]}
        else:
            providers['anthropic'] = {'status': 'not_configured', 'label': 'Claude — sozlanmagan'}

        # ── Serper (Web search) ──────────────────────────────────
        serper_key = getattr(settings, 'SERPER_API_KEY', '')
        if serper_key:
            try:
                resp = http_requests.post(
                    'https://google.serper.dev/search',
                    headers={'X-API-KEY': serper_key, 'Content-Type': 'application/json'},
                    json={'q': 'test', 'num': 1},
                    timeout=5,
                )
                if resp.status_code == 200:
                    providers['serper'] = {'status': 'ok', 'label': 'Serper (Web) — tayyor ✅'}
                elif resp.status_code == 429:
                    providers['serper'] = {'status': 'quota_exceeded', 'label': 'Serper — limit tugagan ⚠️'}
                else:
                    providers['serper'] = {'status': 'error', 'label': f'Serper — xato ({resp.status_code}) ❌'}
            except Exception as exc:
                providers['serper'] = {'status': 'error', 'label': 'Serper — ulanish xatosi ❌', 'error': str(exc)[:80]}
        else:
            providers['serper'] = {'status': 'not_configured', 'label': 'Serper (Web) — sozlanmagan'}

        # ── Active dispatcher model ──────────────────────────────
        active_model = 'gemini'
        active_model_name = providers.get('gemini', {}).get('model', 'gemini-2.0-flash')
        try:
            from services.ai_dispatcher import AIDispatcher
            d = AIDispatcher()
            active_model = d.provider
            active_model_name = d.model_name
        except Exception:
            pass

        # Any provider with status=ok is enough
        any_ok = any(p['status'] == 'ok' for p in providers.values())
        quota_exceeded = [k for k, v in providers.items() if v['status'] == 'quota_exceeded']

        return JsonResponse({
            'ok': any_ok,
            'providers': providers,
            'active_provider': active_model,
            'active_model_name': active_model_name,
            'quota_exceeded': quota_exceeded,
            # Legacy keys for backwards compat
            'gemini_available': providers.get('gemini', {}).get('status') == 'ok',
            'huggingface_available': bool(getattr(settings, 'HUGGINGFACE_API_TOKEN', '')),
            'serper_available': providers.get('serper', {}).get('status') == 'ok',
        })


class AnalysisListView(LoginRequiredMixin, ListView):
    """All analyses (officer view can see all clients)."""
    template_name = 'core/analysis_list.html'
    context_object_name = 'analyses'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        is_officer = hasattr(user, 'profile') and user.profile.is_officer()
        if is_officer:
            return BusinessAnalysisRequest.objects.all().order_by('-created_at')
        return BusinessAnalysisRequest.objects.filter(client=user).order_by('-created_at')


class AnalysisDeleteView(LoginRequiredMixin, View):
    """Delete old analyses from dashboard/list screens."""
    def post(self, request, pk):
        is_officer = hasattr(request.user, 'profile') and request.user.profile.is_officer()
        qs = BusinessAnalysisRequest.objects
        analysis = get_object_or_404(qs if is_officer else qs.filter(client=request.user), pk=pk)

        business_name = analysis.business_type
        try:
            analysis.delete()
            messages.success(request, f"'{business_name}' tahlili o'chirildi.")
        except OperationalError as exc:
            # Some dev DBs may miss optional category tables; fallback to base-row deletion.
            if 'no such table' in str(exc).lower():
                BusinessAnalysisRequest.objects.filter(pk=analysis.pk)._raw_delete(using='default')
                messages.success(request, f"'{business_name}' tahlili o'chirildi.")
            else:
                raise

        next_url = (request.POST.get('next') or '').strip()
        if next_url.startswith('/'):
            return redirect(next_url)
        return redirect('home')


# ── Auth Views ──────────────────────────────────────────────

class LoginView(View):
    template_name = 'core/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('home')
        return render(request, self.template_name)

    def post(self, request):
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect(request.GET.get('next', 'home'))
        messages.error(request, "Login yoki parol noto'g'ri.")
        return render(request, self.template_name, {'username': username})


class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect('login')


class RegisterView(View):
    template_name = 'core/register.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('home')
        return render(request, self.template_name, {'form': UserRegisterForm()})

    def post(self, request):
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if User.objects.filter(username=data['username']).exists():
                form.add_error('username', 'Bu login allaqachon mavjud.')
                return render(request, self.template_name, {'form': form})
            user = User.objects.create_user(
                username=data['username'],
                password=data['password1'],
                first_name=data['first_name'],
                last_name=data['last_name'],
            )
            UserProfile.objects.create(user=user, role='CLIENT')
            login(request, user)
            messages.success(request, f"Xush kelibsiz, {user.first_name}!")
            return redirect('home')
        return render(request, self.template_name, {'form': form})

class SwitchAIProviderView(LoginRequiredMixin, View):
    """Allows Admin/Officer to quickly switch the AI backend via the UI."""
    def get(self, request, provider):
        # We only allow changing to known providers
        if provider not in ['gemini', 'openai', 'anthropic', 'huggingface']:
            messages.error(request, "Noma'lum AI provayderi tanlandi.")
            return redirect(request.META.get('HTTP_REFERER', 'home'))

        from .models import SystemConfiguration
        config = SystemConfiguration.get_solo()
        config.active_ai_provider = provider
        config.save()

        messages.success(request, f"AI Tizimi '{provider.upper()}' modeliga o'zgartirildi!")
        return redirect(request.META.get('HTTP_REFERER', 'home'))


class AnalysisRetryView(LoginRequiredMixin, View):
    """Re-dispatch Celery task for a failed analysis without changing inputs."""
    def post(self, request, pk):
        analysis = get_object_or_404(
            BusinessAnalysisRequest,
            pk=pk,
            client=request.user,
            status__in=['failed', 'pending'],
        )
        analysis.status = 'pending'
        analysis.progress_pct = 0
        analysis.completed_blocks = []
        analysis.warning_flag = False
        analysis.warning_message = ''
        analysis.is_notified = False
        analysis.save(update_fields=['status', 'progress_pct', 'completed_blocks',
                                     'warning_flag', 'warning_message', 'is_notified'])
        try:
            from apps.core.tasks import run_full_analysis
            task = run_full_analysis.delay(analysis.pk)
            analysis.celery_task_id = task.id if hasattr(task, 'id') else ''
            analysis.save(update_fields=['celery_task_id'])
            messages.success(request, "Tahlil qayta boshlandi!")
        except Exception as e:
            analysis.status = 'failed'
            analysis.warning_flag = True
            analysis.warning_message = str(e)
            analysis.save(update_fields=['status', 'warning_flag', 'warning_message'])
            messages.error(request, f"Tahlilni qayta boshlash imkoni bo'lmadi: {e}")
        return redirect('analysis_status_page', pk=analysis.pk)


class AnalysisEditView(LoginRequiredMixin, View):
    """Redirect to the create form pre-filled with saved form data."""
    def get(self, request, pk):
        analysis = get_object_or_404(
            BusinessAnalysisRequest,
            pk=pk,
            client=request.user,
        )
        saved = analysis.form_data_json or {}
        if not saved:
            messages.warning(request, "Eski forma ma'lumotlari saqlanmagan.")
            return redirect('analysis_create')
        # Pass the saved PK so the create view can pre-fill
        return redirect(f"{request.build_absolute_uri('/analysis/new/')}?edit_from={pk}")

class ZalogCheckAPIView(View):
    """
    Check if a given zalog_id exists, and return its total value.
    """
    def get(self, request, *args, **kwargs):
        zalog_id = request.GET.get('zalog_id')
        if not zalog_id:
            return JsonResponse({'error': 'No zalog_id provided'}, status=400)
            
        try:
            zalog = Zalog.objects.get(zalog_id=zalog_id)
            return JsonResponse({
                'found': True,
                'total_value': float(zalog.total_value),
                'property_type': zalog.property_type,
                'owner': f"{zalog.first_name} {zalog.last_name}"
            })
        except Zalog.DoesNotExist:
            return JsonResponse({'found': False, 'error': 'Zalog topilmadi'}, status=404)

class AnalysisNotificationAPIView(LoginRequiredMixin, View):
    """
    Returns a list of completed/failed analyses that haven't been notified yet.
    """
    def get(self, request, *args, **kwargs):
        from .models import BusinessAnalysisRequest
        from django.urls import reverse
        
        # Get unnotified analyses that finished
        analyses = BusinessAnalysisRequest.objects.filter(
            client=request.user,
            status__in=['done', 'failed'],
            is_notified=False
        ).order_by('-updated_at')
        
        notifications = []
        for a in analyses:
            notifications.append({
                'id': a.id,
                'status': a.status,
                'url': reverse('analysis_result' if a.status == 'done' else 'analysis_status_page', args=[a.id])
            })
            # Mark as notified immediately
            a.is_notified = True
            a.save(update_fields=['is_notified'])
            
        return JsonResponse({'notifications': notifications})

