# slm/apps.py
from django.apps import AppConfig


class SlmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'slm'

    def ready(self):
        # Import signal handlers – they register themselves on import
        import slm.signals  # noqa: F401
