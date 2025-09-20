from django.apps import AppConfig


class MedicAuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "medic_auth"

    def ready(self):
        import medic_auth.signals
