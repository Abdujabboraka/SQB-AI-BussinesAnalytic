from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    path('analysis/', include('apps.dashboard.urls')),
    path('analysis/', include('apps.market_analysis.urls')),
    path('analysis/', include('apps.demand_forecast.urls')),
    path('analysis/', include('apps.location_intel.urls')),
    path('analysis/', include('apps.financial_viability.urls')),
    path('analysis/', include('apps.competition_risk.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
