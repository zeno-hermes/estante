"""
Configuração do projeto Estante.

Valores sensíveis (SECRET_KEY, DEBUG, ALLOWED_HOSTS) vêm do ficheiro .env,
que nunca entra no repositório. Ver .env.example para o modelo.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env(nome, default=None, obrigatorio=False):
    """Lê uma variável de ambiente de texto, com erro explícito se faltar."""
    valor = os.environ.get(nome, default)
    if obrigatorio and not valor:
        raise ImproperlyConfigured(
            f"Falta a variável {nome}. Copia .env.example para .env e preenche os valores."
        )
    return valor


def env_bool(nome, default=False):
    """Lê uma variável de ambiente booleana (1/true/yes/sim/on)."""
    return str(env(nome, "true" if default else "false")).strip().lower() in {
        "1",
        "true",
        "yes",
        "sim",
        "on",
    }


# --------------------------------------------------------------------------
# Segurança / ambiente
# --------------------------------------------------------------------------

DEBUG = env_bool("DEBUG", True)

SECRET_KEY = env("SECRET_KEY", obrigatorio=not DEBUG)

if DEBUG and not SECRET_KEY:  # conveniência só em desenvolvimento local
    SECRET_KEY = "django-insecure-chave-de-desenvolvimento-local"

ALLOWED_HOSTS = [
    h.strip() for h in env("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in env("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

# Nginx termina o TLS à frente do Gunicorn.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --------------------------------------------------------------------------
# Aplicações
# --------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "livros",
    "pwa",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# WhiteNoise só serve estáticos em produção (depois de collectstatic); em
# desenvolvimento quem serve é o django.contrib.staticfiles.
if not DEBUG:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "estante.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "pwa.context_processors.versao_offline",
            ],
        },
    },
]

WSGI_APPLICATION = "estante.wsgi.application"

# --------------------------------------------------------------------------
# Base de dados
#
# Em produção o ficheiro fica FORA do checkout Git (DB_PATH), senão o
# `git reset --hard` do deploy mexe-lhe. Em desenvolvimento fica na raiz.
# --------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env("DB_PATH") or BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
            "transaction_mode": "IMMEDIATE",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Autenticação
# --------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/entrar/"
LOGIN_REDIRECT_URL = "/livros/"
LOGOUT_REDIRECT_URL = "/entrar/"

# --------------------------------------------------------------------------
# Internacionalização
# --------------------------------------------------------------------------

LANGUAGE_CODE = "pt-pt"
TIME_ZONE = "Europe/Lisbon"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Estáticos
# --------------------------------------------------------------------------

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Em produção aponta para fora do checkout (ver STATIC_ROOT_DIR no .env.example).
STATIC_ROOT = env("STATIC_ROOT_DIR") or BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

# --------------------------------------------------------------------------
# Email
#
# A aplicação não envia email (as contas são criadas por scripts/create_admin.py),
# mas em produção o Django recusa um backend de desenvolvimento (check mail.E001).
# Fica SMTP configurável por .env; sem EMAIL_HOST aponta a localhost:25, que só é
# usado se algum dia se ativar o "recuperar password" do admin.
# --------------------------------------------------------------------------

if DEBUG:
    MAILERS = {
        "default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"},
    }
else:
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "HOST": env("EMAIL_HOST", "localhost"),
            "PORT": int(env("EMAIL_PORT") or "25"),
            "USER": env("EMAIL_HOST_USER", ""),
            "PASSWORD": env("EMAIL_HOST_PASSWORD", ""),
            "USE_TLS": env_bool("EMAIL_USE_TLS", False),
        }
    }

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "estante@localhost")

# --------------------------------------------------------------------------
# Endurecimento em produção (HTTPS atrás de Nginx + Certbot)
# --------------------------------------------------------------------------

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"

# --------------------------------------------------------------------------
# Registo em ficheiro (produção), útil para diagnosticar deploys
# --------------------------------------------------------------------------

if not DEBUG:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simples": {"format": "{levelname} {asctime} {name} {message}", "style": "{"}
        },
        "handlers": {
            "consola": {"class": "logging.StreamHandler", "formatter": "simples"},
        },
        "root": {"handlers": ["consola"], "level": "INFO"},
    }
