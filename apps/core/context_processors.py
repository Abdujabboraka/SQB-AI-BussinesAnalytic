from django.conf import settings
from django.core.cache import cache


def ai_providers(request):
    from services.ai_dispatcher import PROVIDER_REGISTRY

    from apps.core.models import SystemConfiguration
    try:
        active_provider = SystemConfiguration.get_solo().active_ai_provider
    except Exception:
        active_provider = 'gemini'

    providers = []
    for pid, meta in PROVIDER_REGISTRY.items():
        if pid == 'mock':
            continue
        key_name = meta['settings_key']
        value = getattr(settings, key_name, '') or ''
        if not value.strip():
            continue
        providers.append({
            'id':         pid,
            'name':       meta['name'],
            'icon':       meta['icon'],
            'is_mock':    False,
            'is_active':  pid == active_provider,
            'is_working': cache.get(f'ai_health_{pid}', True),
            'priority':   meta['priority'],
        })

    # Sort by priority so the dropdown order matches the fallback chain.
    providers.sort(key=lambda p: p['priority'])

    # Serper is a web-search service — shown as status-only, not switchable.
    serper_key = getattr(settings, 'SERPER_API_KEY', '') or ''
    serper_configured = bool(serper_key.strip())
    serper_working = cache.get('ai_health_serper', serper_configured)

    return {
        'available_ai_providers': providers,
        'serper_configured':      serper_configured,
        'serper_working':         serper_working,
    }
