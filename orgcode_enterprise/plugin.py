from tutor import hooks

# --------------------------------------------------
# Install package into Open edX Docker image
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
# Register Django app (LMS - production + development)
# --------------------------------------------------
hooks.Filters.ENV_PATCHES.add_items([
    (
        "openedx-lms-production-settings",
        """
# --- orgcode_enterprise: register Django app ---
if "orgcode_enterprise" not in INSTALLED_APPS:
    INSTALLED_APPS.append("orgcode_enterprise")
""",
    ),
    (
        "openedx-lms-development-settings",
        """
# --- orgcode_enterprise: register Django app ---
if "orgcode_enterprise" not in INSTALLED_APPS:
    INSTALLED_APPS.append("orgcode_enterprise")
""",
    ),
])

# --------------------------------------------------
# Register URLs (SAFE for Tutor 21+)
# --------------------------------------------------
hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-lms-common-settings",
        """
# --- orgcode_enterprise: safe URL registration ---
try:
    from django.urls import include, path

    if "urlpatterns" in globals():
        if not any(
            hasattr(p, "urlconf_module") and p.urlconf_module == "orgcode_enterprise.urls"
            for p in urlpatterns
        ):
            urlpatterns += [
                path("api/orgcode/", include("orgcode_enterprise.urls")),
            ]
except Exception:
    pass
""",
    )
)
