from tutor import hooks

# --------------------------------------------------
# Install package into Open edX image
# --------------------------------------------------
hooks.Filters.CONFIG_DEFAULTS.add_item(
    (
        "OPENEDX_EXTRA_PIP_REQUIREMENTS",
        [
            "git+https://github.com/pselleh/orgcode-enterprise.git@main",
        ],
    )
)

# --------------------------------------------------
# Add app to Django settings safely
# --------------------------------------------------
hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-lms-production-settings",
        """
# --- orgcode_enterprise: add Django app safely ---
if "orgcode_enterprise" not in INSTALLED_APPS:
    INSTALLED_APPS.append("orgcode_enterprise")
""",
    )
)

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-lms-development-settings",
        """
# --- orgcode_enterprise: add Django app safely ---
if "orgcode_enterprise" not in INSTALLED_APPS:
    INSTALLED_APPS.append("orgcode_enterprise")
""",
    )
)

# --------------------------------------------------
# Register API URLs in LMS
# --------------------------------------------------
hooks.Filters.URLS.add_item(
    (
        "lms",
        """
from django.urls import path, include

urlpatterns += [
    path("api/orgcode/", include("orgcode_enterprise.urls")),
]
""",
    )
)
