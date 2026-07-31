"""
Django settings for QuattreTV IPTV Middleware.
"""
import os
from pathlib import Path
from datetime import timedelta

from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-this-in-production')

DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'django_celery_beat',
    'django_celery_results',
    # Local apps
    'apps.core',
    'apps.accounts',
    'apps.devices',
    'apps.channels',
    'apps.epg',
    'apps.vod',
    'apps.timeshift',
    'apps.pvr',
    'apps.stalker_api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
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
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'quattretv'),
        'USER': os.getenv('DB_USER', 'quattretv'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'quattretv'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# Cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        'OPTIONS': {
            # Si Redis no responde hay que fallar rapido: la cache es un extra
            # y no puede quedarse colgando las peticiones de los decos.
            'socket_connect_timeout': 1,
            'socket_timeout': 1,
        },
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# Cabeceras de seguridad
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'

# HTTPS. Se activa con BEHIND_TLS_PROXY=True cuando hay un nginx delante
# terminando TLS. Va detrás de una variable a propósito: encenderlo mientras el
# portal se sirve por HTTP dejaría a los decos sin poder entrar.
BEHIND_TLS_PROXY = os.getenv('BEHIND_TLS_PROXY', 'False').lower() in ('true', '1', 'yes')

if BEHIND_TLS_PROXY:
    # nginx nos dice por qué esquema entró la petición.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv('HSTS_SECONDS', '0'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False

    # La redirección la hace nginx, que es más barato que darle la vuelta aquí.
    SECURE_SSL_REDIRECT = False

CSRF_TRUSTED_ORIGINS = [
    origen for origen in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if origen
]

# Internationalization
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'Europe/Madrid'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'apps.stalker_api.authentication.MACAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
}

# CORS
CORS_ALLOWED_ORIGINS = os.getenv(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000'
).split(',')
CORS_ALLOW_CREDENTIALS = True

# Celery
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'default'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# DatabaseScheduler syncs these into the DB on start, so the periodic jobs exist
# without anyone having to create them by hand in the admin.
CELERY_BEAT_SCHEDULE = {
    'epg-actualizar-fuentes': {
        'task': 'apps.epg.tasks.update_all_epg_sources',
        'schedule': crontab(minute=15),
    },
    'epg-limpiar-programas-antiguos': {
        'task': 'apps.epg.tasks.cleanup_old_programs',
        'schedule': crontab(hour=4, minute=30),
    },
    'pvr-enviar-grabaciones': {
        'task': 'apps.pvr.tasks.dispatch_due_recordings',
        'schedule': 60.0,
    },
    'pvr-aplicar-reglas': {
        'task': 'apps.pvr.tasks.apply_recording_rules',
        'schedule': crontab(minute=25),
    },
    'pvr-reconciliar-grabaciones': {
        'task': 'apps.pvr.tasks.reconcile_recordings',
        'schedule': 300.0,
    },
}

# QuattreTV Settings
QUATTRETV = {
    # URL publica de este middleware: los decos y las TV la usan para pedir las
    # playlists de catchup que generamos.
    'PUBLIC_URL': os.getenv('PUBLIC_URL', 'http://localhost:8000'),
    'STREAMING_SERVER_URL': os.getenv('STREAMING_SERVER_URL', 'http://localhost:8080'),
    'TIMESHIFT_ENABLED': os.getenv('TIMESHIFT_ENABLED', 'True').lower() in ('true', '1', 'yes'),
    'TIMESHIFT_HOURS': int(os.getenv('TIMESHIFT_HOURS', '24')),
    'DEFAULT_TIMEZONE': 'Europe/Madrid',
    'EPG_UPDATE_INTERVAL': 3600,  # seconds
    'MAX_DEVICES_PER_USER': 5,
    'MAX_CONCURRENT_STREAMS': 2,
}
