# account/apps.py
from django.apps import AppConfig


class AccountConfig(AppConfig):
    name = "account"

    def ready(self):
        # Import signal handlers so they get registered.
        import account.signals  # noqa: F401
