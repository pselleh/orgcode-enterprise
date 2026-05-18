from django.apps import AppConfig


class OrgcodeEnterpriseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orgcode_enterprise"
    label = "orgcode_enterprise"
    verbose_name = "OrgCode Enterprise"

    def ready(self):
        try:
            from django.urls import include, path
            import lms.urls

            existing = [
                str(p.pattern)
                for p in lms.urls.urlpatterns
            ]

            if "api/orgcode/" not in existing:
                lms.urls.urlpatterns.append(
                    path(
                        "api/orgcode/",
                        include("orgcode_enterprise.urls"),
                    )
                )

        except Exception:
            pass
