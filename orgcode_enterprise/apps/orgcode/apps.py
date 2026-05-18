from django.apps import AppConfig


class OrgcodeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orgcode_enterprise.apps.orgcode"

    plugin_app = {
        "url_config": {
            "lms.djangoapp": {
                "namespace": "orgcode",
                "regex": r"^api/orgcode/",
                "relative_path": "urls",
            }
        }
    }
