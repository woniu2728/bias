"""
Django settings for bias project.
"""

from pathlib import Path
import os

from apps.core.bootstrap_config import load_site_bootstrap

BASE_DIR = Path(__file__).resolve().parent.parent
BOOTSTRAP = load_site_bootstrap(BASE_DIR)


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = BOOTSTRAP.secret_key

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = BOOTSTRAP.debug

FRONTEND_URL = BOOTSTRAP.resolved_frontend_url()
ALLOWED_HOSTS = BOOTSTRAP.resolved_allowed_hosts()

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party apps
    'ninja',
    'ninja_extra',
    'ninja_jwt',
    'corsheaders',
    'django_extensions',
    'channels',

    # Local apps
    'apps.core',
    'apps.users',
    'apps.discussions',
    'apps.posts',
    'apps.notifications',
    'apps.tags',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'apps.core.middleware.StartupStateMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.core.middleware.QueryLoggingMiddleware',
    'apps.core.middleware.MaintenanceModeMiddleware',
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
ASGI_APPLICATION = 'config.asgi.application'

# Database
DB_MODE = BOOTSTRAP.database_mode.strip().lower()

if DB_MODE in {'sqlite', 'sqlite3'}:
    sqlite_name = BOOTSTRAP.sqlite_name or 'db.sqlite3'
    sqlite_path = Path(sqlite_name)
    if not sqlite_path.is_absolute():
        sqlite_path = BASE_DIR / sqlite_path
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': sqlite_path,
            'OPTIONS': {
                'timeout': 10,
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': BOOTSTRAP.db_engine or 'django.db.backends.postgresql',
            'NAME': BOOTSTRAP.db_name or 'bias',
            'USER': BOOTSTRAP.db_user or 'postgres',
            'PASSWORD': BOOTSTRAP.db_password or 'postgres',
            'HOST': BOOTSTRAP.db_host or 'localhost',
            'PORT': BOOTSTRAP.db_port or '5432',
        }
    }

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = BOOTSTRAP.static_url or '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []

# Media files
MEDIA_URL = BOOTSTRAP.media_url or '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS Settings
CORS_ALLOWED_ORIGINS = BOOTSTRAP.resolved_cors_origins()
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = BOOTSTRAP.resolved_csrf_origins()

# Redis Configuration
REDIS_HOST = BOOTSTRAP.redis_host or 'localhost'
REDIS_PORT = BOOTSTRAP.redis_port or '6379'
REDIS_DB = BOOTSTRAP.redis_db or '0'
USE_REDIS = BOOTSTRAP.use_redis

# Cache Configuration
CACHES = (
    {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}',
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }
    if USE_REDIS else
    {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'bias-dev-cache',
        }
    }
)

# Celery Configuration
CELERY_BROKER_URL = BOOTSTRAP.celery_broker_url or (
    f'redis://{REDIS_HOST}:{REDIS_PORT}/1' if USE_REDIS else 'memory://'
)
CELERY_RESULT_BACKEND = BOOTSTRAP.celery_result_backend or (
    f'redis://{REDIS_HOST}:{REDIS_PORT}/2' if USE_REDIS else 'cache+memory://'
)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Channels Configuration
CHANNEL_LAYERS = (
    {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [(REDIS_HOST, int(REDIS_PORT))],
            },
        },
    }
    if USE_REDIS else
    {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }
)

# Email Configuration
EMAIL_BACKEND = BOOTSTRAP.email_backend or 'django.core.mail.backends.console.EmailBackend'
EMAIL_HOST = BOOTSTRAP.email_host or 'smtp.gmail.com'
EMAIL_PORT = int(BOOTSTRAP.email_port or 587)
EMAIL_USE_TLS = BOOTSTRAP.email_use_tls
EMAIL_HOST_USER = BOOTSTRAP.email_host_user or ''
EMAIL_HOST_PASSWORD = BOOTSTRAP.email_host_password or ''
DEFAULT_FROM_EMAIL = BOOTSTRAP.default_from_email or 'noreply@bias.local'

# JWT Settings
NINJA_JWT = {
    'ACCESS_TOKEN_LIFETIME': int(BOOTSTRAP.jwt_access_token_lifetime or 3600),
    'REFRESH_TOKEN_LIFETIME': int(BOOTSTRAP.jwt_refresh_token_lifetime or 86400),
    'ALGORITHM': BOOTSTRAP.jwt_algorithm or 'HS256',
    'SIGNING_KEY': BOOTSTRAP.jwt_secret_key or SECRET_KEY,
}

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# Debug Toolbar (only in DEBUG mode)
ENABLE_DEBUG_TOOLBAR = DEBUG and False

if ENABLE_DEBUG_TOOLBAR:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ['127.0.0.1', 'localhost']
