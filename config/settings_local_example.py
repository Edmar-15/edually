"""
Example template for ``settings_local.py``.

Copy this file to ``settings_local.py`` and replace every ``YOUR_…`` placeholder
with the appropriate value for your environment.  Keep ``settings_local.py``
out of version control (add it to ``.gitignore``) so that secrets never get
checked in.
"""

import os
from pathlib import Path

# --------------------------------------------------------------
# Import the common/base settings first.
# --------------------------------------------------------------
from .settings import *   # noqa: F401,F403

# --------------------------------------------------------------
# SECURITY
# --------------------------------------------------------------
SECRET_KEY = "YOUR_RANDOM_SECRET_KEY"          # e.g. `django.core.management.utils.get_random_secret_key()`

DEBUG = True                                   # Change to ``False`` in production

# --------------------------------------------------------------
# HOSTS
# --------------------------------------------------------------
ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    # "my‑production‑domain.com",
]

# --------------------------------------------------------------
# DATABASE
# --------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",          # replace with `django.db.backends.postgresql` etc. if needed
        "NAME": BASE_DIR / "db.sqlite3",                # for PostgreSQL you might use: os.getenv("POSTGRES_DB")
        "USER": "YOUR_DB_USER",
        "PASSWORD": "YOUR_DB_PASSWORD",
        "HOST": "YOUR_DB_HOST",
        "PORT": "YOUR_DB_PORT",
    }
}

# --------------------------------------------------------------
# GOOGLE OAUTH2
# --------------------------------------------------------------
GOOGLE_CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID"
GOOGLE_CLIENT_SECRET = "YOUR_GOOGLE_CLIENT_SECRET"
GOOGLE_OAUTH_REDIRECT_URI = "http://127.0.0.1:8000/account/login/google/callback/"

# --------------------------------------------------------------
# OPTIONAL: EMAIL (useful when you want to test password‑reset,
#            account‑verification, etc.)
# --------------------------------------------------------------
# EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# EMAIL_HOST = "smtp.example.com"
# EMAIL_PORT = 587
# EMAIL_HOST_USER = "YOUR_SMTP_USER"
# EMAIL_HOST_PASSWORD = "YOUR_SMTP_PASSWORD"
# EMAIL_USE_TLS = True
