"""
Django settings for bias-site project.

Generated from bias-core bootstrap pattern.
"""

from pathlib import Path
import os

from bias_core.conf.bootstrap import load_site_bootstrap
from bias_core.conf.extension_discovery import (
    discover_installed_extension_django_apps,
    discover_extension_migration_modules,
)

BASE_DIR = Path(__file__).resolve().parent.parent
BIAS_EXTENSION_WORKSPACE_ROOT = BASE_DIR.parent
BOOTSTRAP = load_site_bootstrap(BASE_DIR)


def env_int(name: str, default: int) -> int:
    import os
    try:
        return int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = BOOTSTRAP.secret_key

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = BOOTSTRAP.debug

FRONTEND_URL = BOOTSTRAP.resolved_frontend_url()
ALLOWED_HOSTS = BOOTSTRAP.resolved_allowed_hosts()

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third party apps
    "ninja",
    "ninja_extra",
    "ninja_jwt",
    "corsheaders",
    "django_extensions",
    "channels",

    # Core platform
    "bias_core",

    # Extensions (auto-discovered via entry points)
    *discover_installed_extension_django_apps(BASE_DIR),
]

MIGRATION_MODULES = discover_extension_migration_modules(BASE_DIR)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "bias_core.middleware.StartupStateMiddleware",
    "bias_core.middleware.ExtensionErrorHandlingMiddleware",
    "bias_core.middleware.ExtensionRuntimeInvalidationMiddleware",
    "bias_core.middleware.ExtensionCsrfMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "bias_core.middleware.ExtensionThrottleApiMiddleware",
    "bias_core.middleware.ExtensionRequestMiddleware",
    "bias_core.middleware.QueryLoggingMiddleware",
    "bias_core.middleware.MaintenanceModeMiddleware",
    "bias_core.middleware.SecurityHeadersMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.cached.Loader",
                    [
                        "bias_core.extensions.template_loader.ExtensionNamespaceLoader",
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                    ],
                ),
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
TEST_RUNNER = "bias_core.test_runner.BiasDiscoverRunner"
WEB_CONCURRENCY = max(1, env_int("WEB_CONCURRENCY", 1))


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

if BOOTSTRAP.database_mode == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": BOOTSTRAP.db_engine,
            "NAME": BOOTSTRAP.db_name,
            "USER": BOOTSTRAP.db_user,
            "PASSWORD": BOOTSTRAP.db_password,
            "HOST": BOOTSTRAP.db_host,
            "PORT": BOOTSTRAP.db_port,
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / BOOTSTRAP.sqlite_name,
        }
    }


AUTH_USER_MODEL = "users.User"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = BOOTSTRAP.static_url
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

MEDIA_URL = BOOTSTRAP.media_url
MEDIA_ROOT = BASE_DIR / "media"


# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Ninja Extra pagination settings
NINJA_PAGINATION_CLASS = "ninja_extra.pagination.PageNumberPaginationExtra"
NINJA_PAGINATION_PER_PAGE = 20
NINJA_PAGINATION_MAX_LIMIT = 100
NUM_PROXIES = None
DEFAULT_THROTTLE_RATES = None


# Email
EMAIL_BACKEND = BOOTSTRAP.email_backend
EMAIL_HOST = BOOTSTRAP.email_host
EMAIL_PORT = BOOTSTRAP.email_port
EMAIL_USE_TLS = BOOTSTRAP.email_use_tls
EMAIL_HOST_USER = BOOTSTRAP.email_host_user
EMAIL_HOST_PASSWORD = BOOTSTRAP.email_host_password
DEFAULT_FROM_EMAIL = BOOTSTRAP.default_from_email


# CORS
CORS_ALLOWED_ORIGINS = BOOTSTRAP.resolved_cors_origins()
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = BOOTSTRAP.resolved_csrf_origins()


# Ninja JWT
NINJA_JWT = {
    "ALGORITHM": BOOTSTRAP.jwt_algorithm,
    "SIGNING_KEY": BOOTSTRAP.jwt_secret_key,
    "ACCESS_TOKEN_LIFETIME": BOOTSTRAP.jwt_access_token_lifetime,
    "REFRESH_TOKEN_LIFETIME": BOOTSTRAP.jwt_refresh_token_lifetime,
}


# Celery
if BOOTSTRAP.celery_broker_url:
    CELERY_BROKER_URL = BOOTSTRAP.celery_broker_url
    CELERY_RESULT_BACKEND = BOOTSTRAP.celery_result_backend


# Cache
if BOOTSTRAP.use_redis:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": f"redis://{BOOTSTRAP.redis_host}:{BOOTSTRAP.redis_port}/{BOOTSTRAP.redis_db}",
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }


# Channels
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

if BOOTSTRAP.use_redis:
    CHANNEL_LAYERS["default"] = {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(BOOTSTRAP.redis_host, int(BOOTSTRAP.redis_port))],
        },
    }


# Debug Toolbar
ENABLE_DEBUG_TOOLBAR = DEBUG and os.getenv("ENABLE_DEBUG_TOOLBAR", "").lower() in {"1", "true", "yes"}
if ENABLE_DEBUG_TOOLBAR:
    INSTALLED_APPS.append("debug_toolbar")
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
    INTERNAL_IPS = ["127.0.0.1", "localhost"]


# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}

