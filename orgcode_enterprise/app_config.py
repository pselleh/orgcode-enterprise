from django.apps import AppConfig

try:
    from edx_django_utils.plugins import PluginURLs
    from openedx.core.djangoapps.plugins.constants import ProjectType
except ImportError:  # Allows packaging and migration checks outside edx-platform.
    PluginURLs = None
    ProjectType = None


class OrgcodeEnterpriseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orgcode_enterprise"
    label = "orgcode_enterprise"
    verbose_name = "OrgCode Enterprise"
    if PluginURLs and ProjectType:
        plugin_app = {
            PluginURLs.CONFIG: {
                ProjectType.LMS: {
                    PluginURLs.NAMESPACE: "orgcode_enterprise",
                    PluginURLs.REGEX: r"^api/orgcode/",
                    PluginURLs.RELATIVE_PATH: "urls",
                }
            }
        }
