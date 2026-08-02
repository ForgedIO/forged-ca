"""Test settings — SQLite in memory so the suite runs on any dev box.

Production and the testbed run PostgreSQL (see `base.py`). Tests deliberately
do not, because a suite that only runs on the one host with Postgres installed
is a suite nobody runs. Django 4.2 supports `JSONField` on SQLite, which is the
only Postgres-specific feature the models rely on today.

If a future slice depends on real Postgres behaviour (full-text search, array
fields, advisory locks), add a separate Postgres-backed test settings module
rather than switching this one back — keep the fast path fast.

Use via: DJANGO_SETTINGS_MODULE=forgedca.settings.test
"""
from forgedca.settings.base import *  # noqa: F401, F403

DEBUG = False

# encrypted_model_fields builds its Fernet crypter when the app registry loads
# and raises ImproperlyConfigured on a missing or malformed key, so tests need
# a real one. Assign the setting directly rather than via os.environ: this
# package's __init__.py does `from .base import *`, so base.py has already run
# and already read the environment by the time this module executes. Setting
# the env var here would be too late and silently leave the key empty.
#
# This value is public, fixed, and test-only. It never protects real data.
FIELD_ENCRYPTION_KEY = "zxKz9Yk3vQ7nB2mF5tH8wJ1cR4dS6gP0aL_eU3iO7yM="

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Tests create a lot of users; the default PBKDF2 hasher dominates runtime.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Keep log output out of /var/log (not writable by a dev user) and out of the
# test runner's stdout.
LOGGING["handlers"]["file"]["filename"] = "/tmp/forgedca-test.log"  # noqa: F405

# Celery must not try to reach Redis during tests.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
