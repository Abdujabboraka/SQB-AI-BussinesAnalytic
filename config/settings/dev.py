from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Use in-memory cache / dummy for dev (no Redis needed to start)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Override Celery to use eager mode (tasks run synchronously in dev — no worker needed)
CELERY_TASK_ALWAYS_EAGER = True   # Run tasks synchronously in dev — no Redis worker needed
CELERY_TASK_EAGER_PROPAGATES = True

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
