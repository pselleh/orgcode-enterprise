from django.apps import AppConfig


class OrgcodeEnterpriseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orgcode_enterprise"

    def ready(self):
        # Force models import
        import orgcode_enterprise.models
