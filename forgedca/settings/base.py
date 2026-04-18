import logging.handlers
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")
_prod_env = Path("/opt/forgedca/.env")
if _prod_env.is_file() and os.access(_prod_env, os.R_OK):
    load_dotenv(_prod_env)

SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-default-change-me")

DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")

_raw_hosts = os.environ.get("ALLOWED_HOSTS", "*")
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()]

SITE_ID = 1

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.microsoft",
    "apps.core",
    "apps.wizard",
    "apps.authconfig",
    "apps.emailconfig",
    "apps.nodes",
    "apps.ca",
    "apps.federation",
    "apps.issuance",
    "apps.acme",
    "apps.templates_app",
    "apps.trust",
    "apps.dashboard",
    "apps.ceremony",
    "apps.truststore",
    "apps.auditlog",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    # Order matters: force password change first, then MFA setup, then the
    # install wizard. No middleware below these should run against an admin
    # who hasn't gone through the pre-wizard hygiene flow.
    "apps.core.middleware.ForcePasswordChangeMiddleware",
    "apps.core.middleware.ForceMFASetupMiddleware",
    "apps.wizard.middleware.WizardRedirectMiddleware",
]

ROOT_URLCONF = "forgedca.urls"
WSGI_APPLICATION = "forgedca.wsgi.application"
ASGI_APPLICATION = "forgedca.asgi.application"

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
                "apps.nodes.helpers.context_processors.node_config",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "forgedca"),
        "USER": os.environ.get("DB_USER", "forgedca"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/0")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]

FIELD_ENCRYPTION_KEY = os.environ.get("FIELD_ENCRYPTION_KEY", "")

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

ACCOUNT_EMAIL_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "username"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True
ACCOUNT_SIGNUP_REDIRECT_URL = "/"
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# Logging — file + optional syslog forwarder.
# Syslog destination is configured from the DB-backed SyslogConfig model at
# runtime by apps.core.apps.CoreConfig.ready(); this dict just defines the
# static file handler and a root logger that will pick up any additional
# handlers registered at startup.
_log_file = os.environ.get("DJANGO_LOG_FILE", "/var/log/forgedca/django.log")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s %(levelname)s %(name)s %(process)d %(message)s",
        },
        "syslog": {
            "format": "forgedca[%(process)d]: %(name)s %(levelname)s %(message)s",
        },
    },
    "handlers": {
        "file": {
            "class": "logging.FileHandler",
            "filename": _log_file,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["file"],
        "level": "WARNING",
    },
    "loggers": {
        "django.request": {
            "handlers": ["file"],
            "level": "ERROR",
            "propagate": False,
        },
        "forgedca": {
            "handlers": ["file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

HELP_DIR = BASE_DIR / "help"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

WEB_PORT = int(os.environ.get("WEB_PORT", "8443"))

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@forgedca.local"

# Path to step-ca state and config — used by apps.ca for rendering ca.json,
# managing keys, and invoking the privileged helper.
STEP_CA_CONFIG_DIR = Path(os.environ.get("STEP_CA_CONFIG_DIR", "/etc/step-ca"))
STEP_CA_DATA_DIR = Path(os.environ.get("STEP_CA_DATA_DIR", "/var/lib/step-ca"))
FORGEDCA_HELPER_BIN = os.environ.get("FORGEDCA_HELPER_BIN", "/opt/forgedca/bin/forgedca-ca-helper")

# step-ca's own Postgres DB (separate from the forgedca app DB above). Both
# live on the same Postgres cluster provisioned by install.sh.
STEP_CA_DB = {
    "NAME": os.environ.get("STEP_CA_DB_NAME", "step_ca"),
    "USER": os.environ.get("STEP_CA_DB_USER", "step_ca"),
    "PASSWORD": os.environ.get("STEP_CA_DB_PASSWORD", ""),
    "HOST": os.environ.get("STEP_CA_DB_HOST", "127.0.0.1"),
    "PORT": os.environ.get("STEP_CA_DB_PORT", "5432"),
}
