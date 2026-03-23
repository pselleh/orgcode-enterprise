from tutor import hooks

# --------------------------------------------------
# Install package into Open edX Docker image (FIXED)
# --------------------------------------------------
hooks.Filters.CONFIG_DEFAULTS.add_items([
    (
        "OPENEDX_EXTRA_PIP_REQUIREMENTS",
        ["git+https://github.com/pselleh/orgcode-enterprise.git@main"],
    ),
])

# --------------------------------------------------
# Register Django app (LMS - production + development)
# --------------------------------------------------
hooks.Filters.ENV_PATCHES.add_items([
    (
        "openedx-lms-production-settings",
        """
if "orgcode_enterprise" not in INSTALLED_APPS:
    INSTALLED_APPS.append("orgcode_enterprise")
""",
    ),
    (
        "openedx-lms-development-settings",
        """
if "orgcode_enterprise" not in INSTALLED_APPS:
    INSTALLED_APPS.append("orgcode_enterprise")
""",
    ),
])

# --------------------------------------------------
# Register URLs (safe, guarded)
# --------------------------------------------------
hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-lms-common-settings",
        """
try:
    from django.urls import include, path

    if "urlpatterns" in globals():
        if not any("orgcode_enterprise.urls" in str(p) for p in urlpatterns):
            urlpatterns += [
                path("api/orgcode/", include("orgcode_enterprise.urls")),
            ]
except Exception:
    pass
""",
    )
)
