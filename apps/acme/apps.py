from django.apps import AppConfig


class ACMEConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.acme"
    verbose_name = "ACME Provisioners"
