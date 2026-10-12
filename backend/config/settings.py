"""Django settings for the weather-aware truck routing API.

All environment-specific values come from environment variables (see .env.example).
The service is stateless: no database, no sessions, no authentication.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    NUM_PROXIES=(int, 0),
    HTTP_CONNECT_TIMEOUT_S=(float, 3.0),
    HTTP_READ_TIMEOUT_S=(float, 10.0),
    THROTTLE_ANALYZE_RATE=(str, "20/min"),
    THROTTLE_HEATMAP_RATE=(str, "20/min"),
    THROTTLE_GEOCODE_RATE=(str, "120/min"),
    LOG_LEVEL=(str, "INFO"),
    REDIS_URL=(str, ""),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "corsheaders",
    "rest_framework",
    "routing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# Route analysis is computed per request from live provider data; nothing is persisted.
DATABASES: dict = {}

# Provider responses (routes, weather, geocodes) and DRF throttle counters live in Redis, shared
# by every worker. Without REDIS_URL (tests, quick local runs) an in-process cache stands in.
REDIS_URL = env("REDIS_URL")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "trw",
            "TIMEOUT": 15 * 60,
            # Short timeouts: a slow or unreachable Redis becomes a cache miss, not a hung request.
            "OPTIONS": {"socket_connect_timeout": 1, "socket_timeout": 1},
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "provider-cache",
            "TIMEOUT": 15 * 60,
        }
    }

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

# --- External providers -------------------------------------------------------

HERE_API_KEY = env("HERE_API_KEY", default="")
HERE_ROUTING_URL = env("HERE_ROUTING_URL", default="https://router.hereapi.com/v8/routes")
HERE_GEOCODE_URL = env("HERE_GEOCODE_URL", default="https://geocode.search.hereapi.com/v1/geocode")
HERE_AUTOSUGGEST_URL = env(
    "HERE_AUTOSUGGEST_URL", default="https://autosuggest.search.hereapi.com/v1/autosuggest"
)
OPEN_METEO_URL = env("OPEN_METEO_URL", default="https://api.open-meteo.com/v1/forecast")

HTTP_CONNECT_TIMEOUT_S = env("HTTP_CONNECT_TIMEOUT_S")
HTTP_READ_TIMEOUT_S = env("HTTP_READ_TIMEOUT_S")

# --- Django REST Framework ----------------------------------------------------

REST_FRAMEWORK = {
    # Public, stateless API: no auth backends, so django.contrib.auth is not needed.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_THROTTLE_CLASSES": ["routing.throttling.FailOpenScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "analyze": env("THROTTLE_ANALYZE_RATE"),
        "heatmap": env("THROTTLE_HEATMAP_RATE"),
        "geocode": env("THROTTLE_GEOCODE_RATE"),
    },
    # Client IP comes from X-Forwarded-For when deployed behind the host's proxy.
    "NUM_PROXIES": env("NUM_PROXIES") or None,
    "EXCEPTION_HANDLER": "routing.exceptions.api_exception_handler",
}

# --- CORS ---------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_METHODS = ["GET", "POST", "OPTIONS"]
# The frontend reads Retry-After on 429/503 to count down before retrying; cross-origin
# responses hide it from JavaScript unless it is exposed.
CORS_EXPOSE_HEADERS = ["Retry-After"]

# --- Security (production) ----------------------------------------------------

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# Requests are small JSON bodies; reject anything unexpectedly large.
DATA_UPLOAD_MAX_MEMORY_SIZE = 64 * 1024

# --- Logging ------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "default"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL")},
    "loggers": {
        # httpx logs full request URLs at INFO, which can include API keys.
        "httpx": {"level": "WARNING"},
    },
}

SILENCED_SYSTEM_CHECKS = [
    # No cookies or sessions are used, so there is no ambient credential for CSRF to protect.
    "security.W003",
    # HSTS preload is a long-lived, hard-to-undo commitment for the domain; opt in deliberately.
    "security.W021",
]
