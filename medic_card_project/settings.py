import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET") or "1234"

DEBUG = False

# Настройки сайта
if not DEBUG:
    SITE_URL = 'https://test-med.ru'
    DEFAULT_HTTP_PROTOCOL = 'https'
    ALLOWED_HOSTS = ['91.218.244.233', 'test-med.ru', '.test-med.ru', "django", "localhost", "127.0.0.1",  '0.0.0.0', ]
else:
    SITE_URL = 'http://localhost:8000'
    DEFAULT_HTTP_PROTOCOL = 'http'
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', 'django']

# CSRF настройки для Caddy
CSRF_TRUSTED_ORIGINS = [
    'https://test-med.ru',
    'https://www.test-med.ru',
    'https://91.218.244.233',
]

# Настройки для работы за обратным прокси
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# В production включаем безопасные настройки
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# Cookie настройки
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'django.contrib.sites',
    'django.contrib.sitemaps',
    "crispy_forms",
    "crispy_bootstrap5",
    "medic_card",
    "medic_auth",
]

SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "medic_card_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

UNFOLD = {
    "SITE_TITLE": "Медицинские карты",
    "SITE_HEADER": "Админ-панель",
    "SITE_ICON": "/static/icon/main.png",
    "THEME": "auto",
}

WSGI_APPLICATION = "medic_card_project.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db/db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "medic_auth.forms.CustomPasswordValidator",
    },
]

SESSION_COOKIE_AGE = 1209600

LANGUAGE_CODE = "ru"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'