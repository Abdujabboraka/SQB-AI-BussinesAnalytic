"""
AI Dispatcher for BiznesAI.
Routes generation tasks to the active AI provider configured in the Django Admin.
"""
import logging
from apps.core.models import SystemConfiguration

logger = logging.getLogger(__name__)

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
        if self.provider == 'openai':
            from services.openai_service import OpenAIService
            from django.conf import settings
            api_key = (self.config.openai_api_key if self.config else None) or getattr(settings, 'OPENAI_API_KEY', '')
            return OpenAIService(api_key=api_key)
        elif self.provider == 'anthropic':
            from services.anthropic_service import AnthropicService
            from django.conf import settings
            api_key = (self.config.anthropic_api_key if self.config else None) or getattr(settings, 'ANTHROPIC_API_KEY', '')
            return AnthropicService(api_key=api_key)
        elif self.provider == 'huggingface':
            from services.huggingface_gen_service import HuggingFaceGenService
            from django.conf import settings
            api_key = getattr(settings, 'HUGGINGFACE_API_TOKEN', None)
            return HuggingFaceGenService(api_key=api_key)
        elif self.provider == 'mock':
            from services.openai_service import OpenAIService
            return OpenAIService(api_key=None)
        else:
            # Default to gemini
            from services.gemini_service import GeminiService
            from django.conf import settings
            api_key = (self.config.gemini_api_key if self.config else None) or getattr(settings, 'GEMINI_API_KEY', '')
            return GeminiService(api_key=api_key)

    @property
    def model(self):
        return getattr(self._service, 'model', getattr(self._service, 'model_name', None))

    @property
    def model_name(self):
        return getattr(self._service, 'model_name', f"Unknown ({self.provider})")

    def _call_with_fallback(self, method_name, *args, **kwargs):
        from django.core.cache import cache
        fallback_order = ['gemini', 'openai', 'anthropic', 'huggingface']
        if self.provider in fallback_order:
            fallback_order.remove(self.provider)
        fallback_order.insert(0, self.provider)

        for provider in fallback_order:
            cache_key = f'ai_health_{provider}'
            is_healthy = cache.get(cache_key, True)

            if not is_healthy:
                logger.info(f"Skipping '{provider}' as it is marked unhealthy in cache.")
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
                    return result
                else:
                    logger.warning(f"Provider '{provider}' returned mock or None. Marking unhealthy.")
                    cache.set(cache_key, False, timeout=3600)
            except Exception as e:
                logger.error(f"Error calling {method_name} on {provider}: {e}")
                cache.set(cache_key, False, timeout=3600)

        # If all fail, use mock
        logger.warning(f"All AI providers failed for {method_name}. Using mock.")
        self.provider = 'mock'
        self._service = self._init_service()
        # Ensure we call the correct mock fallback in the service
        method = getattr(self._service, method_name)
        return method(*args, **kwargs)

    def analyze_market(self, *args, **kwargs):
        return self._call_with_fallback('analyze_market', *args, **kwargs)

    def analyze_demand(self, *args, **kwargs):
        return self._call_with_fallback('analyze_demand', *args, **kwargs)

    def evaluate_location(self, *args, **kwargs):
        return self._call_with_fallback('evaluate_location', *args, **kwargs)

    def analyze_financial_viability(self, *args, **kwargs):
        # Mapped from assess_finance if needed, but we standardized service names now
        return self._call_with_fallback('analyze_financial_viability', *args, **kwargs)

    def analyze_competition(self, *args, **kwargs):
        # Mapped from analyze_risks if needed
        return self._call_with_fallback('analyze_competition', *args, **kwargs)

    def final_decision(self, *args, **kwargs):
        return self._call_with_fallback('final_decision', *args, **kwargs)
    
    # Category-specific passthroughs
    def analyze_hotel(self, *args, **kwargs):
        return self._call_with_fallback('analyze_hotel', *args, **kwargs)
    
    def analyze_construction(self, *args, **kwargs):
        return self._call_with_fallback('analyze_construction', *args, **kwargs)
    
    def analyze_textile(self, *args, **kwargs):
        return self._call_with_fallback('analyze_textile', *args, **kwargs)
    
    def analyze_trade(self, *args, **kwargs):
        return self._call_with_fallback('analyze_trade', *args, **kwargs)
