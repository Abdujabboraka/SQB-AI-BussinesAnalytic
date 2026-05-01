"""
AI Dispatcher for BiznesAI.
Routes generation tasks to the active AI provider configured in the Django Admin.
Adding any API key to .env is enough — the provider appears automatically everywhere.
"""
import logging
import datetime
from django.conf import settings
from apps.core.models import SystemConfiguration

logger = logging.getLogger(__name__)

# Central registry — source of truth for every place that lists providers.
# priority: lower = tried first in fallback chain.
PROVIDER_REGISTRY = {
    'gemini':      {'name': 'Google Gemini',      'icon': 'bi-google',    'settings_key': 'GEMINI_API_KEY',        'priority': 1},
    'openai':      {'name': 'OpenAI GPT',         'icon': 'bi-chat-dots', 'settings_key': 'OPENAI_API_KEY',        'priority': 2},
    'anthropic':   {'name': 'Claude (Anthropic)',  'icon': 'bi-stars',     'settings_key': 'ANTHROPIC_API_KEY',     'priority': 3},
    'aicc':        {'name': 'AI.CC Proxy',         'icon': 'bi-cloud',     'settings_key': 'AICC_API_KEY',          'priority': 4},
    'openrouter':  {'name': 'OpenRouter',          'icon': 'bi-diagram-3', 'settings_key': 'OPENROUTER_API_KEY',    'priority': 5},
    'apifreellm':  {'name': 'FreeLLM (Llama-3)',   'icon': 'bi-cpu',       'settings_key': 'APIFREELLM_API_KEY',    'priority': 6},
    'huggingface': {'name': 'HuggingFace',         'icon': 'bi-braces',    'settings_key': 'HUGGINGFACE_API_TOKEN', 'priority': 7},
    'mock':        {'name': 'Test Rejimi (Mock)',  'icon': 'bi-bug',       'settings_key': None,                    'priority': 99},
}

# Flat label map derived from registry — kept for backwards compatibility.
PROVIDER_LABELS = {pid: meta['name'] for pid, meta in PROVIDER_REGISTRY.items()}


def get_configured_providers() -> list:
    """Return provider IDs that have a non-empty API key in settings, sorted by priority."""
    configured = []
    for pid, meta in PROVIDER_REGISTRY.items():
        if pid == 'mock':
            continue
        key_name = meta['settings_key']
        value = getattr(settings, key_name, '') or ''
        if value.strip():
            configured.append((meta['priority'], pid))
    configured.sort()
    return [pid for _, pid in configured]


class AIDispatcher:
    def __init__(self):
        try:
            self.config = SystemConfiguration.get_solo()
            self.provider = self.config.active_ai_provider
        except Exception as e:
            logger.warning(f"Failed to load SystemConfiguration, defaulting to gemini: {e}")
            self.provider = 'gemini'
            self.config = None

        self._service = self._init_service()

    def _init_service(self):
        provider = self.provider
        cfg = self.config

        if provider == 'openai':
            from services.openai_service import OpenAIService
            api_key = (getattr(cfg, 'openai_api_key', None) if cfg else None) or getattr(settings, 'OPENAI_API_KEY', '')
            return OpenAIService(api_key=api_key)

        elif provider == 'anthropic':
            from services.anthropic_service import AnthropicService
            api_key = (getattr(cfg, 'anthropic_api_key', None) if cfg else None) or getattr(settings, 'ANTHROPIC_API_KEY', '')
            return AnthropicService(api_key=api_key)

        elif provider == 'huggingface':
            from services.huggingface_gen_service import HuggingFaceGenService
            api_key = getattr(settings, 'HUGGINGFACE_API_TOKEN', '')
            return HuggingFaceGenService(api_key=api_key)

        elif provider == 'aicc':
            from services.aicc_service import AICCService
            api_key = (getattr(cfg, 'aicc_api_key', None) if cfg else None) or getattr(settings, 'AICC_API_KEY', '')
            api_url = getattr(settings, 'AICC_URL', '')
            return AICCService(api_key=api_key, api_url=api_url)

        elif provider == 'openrouter':
            from services.openrouter_service import OpenRouterService
            api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
            return OpenRouterService(api_key=api_key)

        elif provider == 'apifreellm':
            from services.apifreellm_service import ApiFreeLLMService
            api_key = getattr(settings, 'APIFREELLM_API_KEY', '')
            return ApiFreeLLMService(api_key=api_key)

        elif provider == 'mock':
            from services.openai_service import OpenAIService
            return OpenAIService(api_key=None)

        else:
            # Default: gemini
            from services.gemini_service import GeminiService
            api_key = (getattr(cfg, 'gemini_api_key', None) if cfg else None) or getattr(settings, 'GEMINI_API_KEY', '')
            return GeminiService(api_key=api_key)

    @property
    def model(self):
        return getattr(self._service, 'model', getattr(self._service, 'model_name', None))

    @property
    def model_name(self):
        return getattr(self._service, 'model_name', f"Unknown ({self.provider})")

    def _save_provider_alert(self, from_provider, to_provider, reason, is_critical):
        try:
            from django.core.cache import cache
            existing = cache.get('ai_provider_switch_alert') or {}
            if existing.get('from_provider') == from_provider and existing.get('to_provider') == to_provider:
                return
            cache.set('ai_provider_switch_alert', {
                'from_provider': from_provider,
                'to_provider':   to_provider,
                'from_label':    PROVIDER_LABELS.get(from_provider, from_provider),
                'to_label':      PROVIDER_LABELS.get(to_provider, to_provider),
                'reason':        reason,
                'is_critical':   is_critical,
                'at':            datetime.datetime.now().isoformat(),
            }, 7200)
        except Exception as exc:
            logger.warning(f"Failed to save provider alert: {exc}")

    def _call_with_fallback(self, method_name, *args, **kwargs):
        from django.core.cache import cache
        original_provider = self.provider

        # Build fallback chain: active provider first, then all other configured ones in priority order.
        all_configured = get_configured_providers()
        fallback_order = [self.provider] + [p for p in all_configured if p != self.provider]

        for provider in fallback_order:
            cache_key = f'ai_health_{provider}'
            is_healthy = cache.get(cache_key, True)

            if not is_healthy:
                logger.info(f"Skipping '{provider}' — marked unhealthy in cache.")
                continue

            if provider != self.provider:
                logger.warning(f"Failing over to '{provider}'.")
                self.provider = provider
                if self.config:
                    self.config.active_ai_provider = provider
                    self.config.save(update_fields=['active_ai_provider'])
                self._service = self._init_service()

            try:
                method = getattr(self._service, method_name)
                result = method(*args, **kwargs)
                if result and not result.get('is_mock'):
                    cache.set(cache_key, True, timeout=3600)
                    if provider != original_provider:
                        self._save_provider_alert(
                            from_provider=original_provider,
                            to_provider=provider,
                            reason=f'{PROVIDER_LABELS.get(original_provider, original_provider)} xatolik qaytardi',
                            is_critical=False,
                        )
                    return result
                else:
                    logger.warning(f"Provider '{provider}' returned mock/None — marking unhealthy.")
                    cache.set(cache_key, False, timeout=3600)
            except Exception as e:
                logger.error(f"Error calling {method_name} on {provider}: {e}")
                cache.set(cache_key, False, timeout=3600)

        # All real providers exhausted — fall back to mock.
        logger.warning(f"All AI providers failed for {method_name}. Using mock.")
        self._save_provider_alert(
            from_provider=original_provider,
            to_provider='mock',
            reason='Barcha AI provayderlar ishlamay qoldi',
            is_critical=True,
        )
        self.provider = 'mock'
        self._service = self._init_service()
        return getattr(self._service, method_name)(*args, **kwargs)

    # ── Public passthroughs ──────────────────────────────────────

    def analyze_market(self, *args, **kwargs):
        return self._call_with_fallback('analyze_market', *args, **kwargs)

    def analyze_demand(self, *args, **kwargs):
        return self._call_with_fallback('analyze_demand', *args, **kwargs)

    def evaluate_location(self, *args, **kwargs):
        return self._call_with_fallback('evaluate_location', *args, **kwargs)

    def analyze_financial_viability(self, *args, **kwargs):
        return self._call_with_fallback('analyze_financial_viability', *args, **kwargs)

    def analyze_competition(self, *args, **kwargs):
        return self._call_with_fallback('analyze_competition', *args, **kwargs)

    def final_decision(self, *args, **kwargs):
        return self._call_with_fallback('final_decision', *args, **kwargs)

    def analyze_hotel(self, *args, **kwargs):
        return self._call_with_fallback('analyze_hotel', *args, **kwargs)

    def analyze_construction(self, *args, **kwargs):
        return self._call_with_fallback('analyze_construction', *args, **kwargs)

    def analyze_textile(self, *args, **kwargs):
        return self._call_with_fallback('analyze_textile', *args, **kwargs)

    def analyze_trade(self, *args, **kwargs):
        return self._call_with_fallback('analyze_trade', *args, **kwargs)
