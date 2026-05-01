"""
BiznesAI — Main Django Settings (dev mode)
Loaded by: manage.py, wsgi.py (config.settings)
"""

from pathlib import Path

try:
    from decouple import config
except ImportError:
    import os
    def config(key, default='', cast=None):
        val = os.environ.get(key, default)
        return cast(val) if cast else val

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security ────────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY', default='django-insecure-biznesai-dev-key-change-in-prod-1234567890')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = ['*']

# ── Apps ─────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Internal apps
    'apps.core',
    'apps.market_analysis',
    'apps.demand_forecast',
    'apps.location_intel',
    'apps.financial_viability',
    'apps.competition_risk',
    'apps.dashboard',
    'apps.category_analysis',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.ai_providers',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ── Database ──────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ── Password Validation ───────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Internationalisation ──────────────────────────────────────
LANGUAGE_CODE = 'uz'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

# ── Static / Media ────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'services' / 'static',   # charts.js, map.js, theme.css live here
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Auth ──────────────────────────────────────────────────────
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# ── Celery ────────────────────────────────────────────────────
CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Tashkent'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 minutes per task
CELERY_TASK_ALWAYS_EAGER = True    # Sync execution in dev — no Redis worker needed
CELERY_TASK_EAGER_PROPAGATES = True

# ── AI Service Keys ───────────────────────────────────────────
GEMINI_API_KEY        = config('GEMINI_API_KEY', default='')
GEMINI_MODEL          = config('GEMINI_MODEL',   default='gemini-2.0-flash')
HUGGINGFACE_API_TOKEN = config('HUGGINGFACE_API_TOKEN', default='')
OPENAI_API_KEY        = config('OPENAI_API_KEY', default=config('openai_api_key', default=''))
ANTHROPIC_API_KEY     = config('ANTHROPIC_API_KEY', default='')
SERPER_API_URL        = config('SERPER_API_URL', default='https://google.serper.dev')
SERPER_API_KEY        = config('SERPER_API_KEY', default='')

# Auto-detected extended providers — add key to .env and they appear automatically
AICC_API_KEY       = config('AICC_API_KEY',  default='')
AICC_URL           = config('AICC_URL',       default='https://api.ai.cc/v1')
AICC_MODEL         = config('AICC_MODEL',     default='gpt-4o-mini')

OPENROUTER_API_KEY = (
    config('OPENROUTER_API_KEY', default='') or
    config('openrouter_ai_api_key', default='')
)
OPENROUTER_URL     = config('OPENROUTER_URL',     default='https://openrouter.ai/api/v1')
OPENROUTER_MODEL   = config('OPENROUTER_MODEL',   default='openai/gpt-4o-mini')

APIFREELLM_API_KEY = (
    config('APIFREELLM_API_KEY', default='') or
    config('apifreellm_API_KEY', default='')
)
APIFREELLM_URL     = (
    config('APIFREELLM_URL', default='') or
    config('apifreellm_url', default='https://apifreellm.com/api/v1/chat')
)

# ── App-level constants ───────────────────────────────────────
ANALYSIS_BLOCK_WEIGHTS = {
    'A': 0.20,
    'B': 0.20,
    'C': 0.25,
    'D': 0.25,
    'E': 0.10,
}

# ── Email (dev: console) ──────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ── Cache (dev: in-memory) ────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
