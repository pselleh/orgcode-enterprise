from django.apps import AppConfig


class OrgcodeEnterpriseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orgcode_enterprise"
    label = "orgcode_enterprise"
    verbose_name = "OrgCode Enterprise"

    plugin_app = {
        "url_config": {
            "lms.djangoapp": {
                "namespace": "orgcode_enterprise",
                "regex": r"^api/orgcode/",
                "relative_path": "urls",
            }
        }
    }
