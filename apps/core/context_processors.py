from django.conf import settings


def ai_providers(request):
    providers = []

    if getattr(settings, 'GEMINI_API_KEY', None):
        providers.append({
            'id': 'gemini',
            'name': 'Google Gemini',
            'icon': 'bi-google',
            'is_mock': False,
        })

    if getattr(settings, 'ANTHROPIC_API_KEY', None):
        providers.append({
            'id': 'anthropic',
            'name': 'Claude (Anthropic)',
            'icon': 'bi-stars',
            'is_mock': False,
        })

    has_openai = getattr(settings, 'OPENAI_API_KEY', None) or getattr(settings, 'openai_api_key', None)
    if has_openai:
        providers.append({
            'id': 'openai',
            'name': 'OpenAI GPT-4',
            'icon': 'bi-chat-dots',
            'is_mock': False,
        })

    if getattr(settings, 'HUGGINGFACE_API_TOKEN', None):
        providers.append({
            'id': 'huggingface',
            'name': 'HuggingFace',
            'icon': 'bi-braces',
            'is_mock': False,
        })

    from apps.core.models import SystemConfiguration
    try:
        active_provider = SystemConfiguration.get_solo().active_ai_provider
    except:
        active_provider = 'gemini'

    for p in providers:
        p['is_active'] = (p['id'] == active_provider)

    return {'available_ai_providers': providers}
