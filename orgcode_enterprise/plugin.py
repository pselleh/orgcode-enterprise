from tutor import hooks

# ==================================================
# COPY orgcode_enterprise INTO IMAGE
# ==================================================

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-dockerfile-pre",
        """
# Copy orgcode_enterprise plugin into image
COPY plugins/orgcode-enterprise /openedx/requirements/orgcode-enterprise
""",
    )
)

# ==================================================
# INSTALL PACKAGE INTO OPENEDX
# ==================================================

hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        (
            "OPENEDX_EXTRA_PIP_REQUIREMENTS",
            ["file:///openedx/requirements/orgcode-enterprise"],
        ),
    ]
)

# ==================================================
# REGISTER DJANGO APP
# ==================================================

hooks.Filters.ENV_PATCHES.add_items(
    [
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
    ]
)

# ==================================================
# REGISTER URLS (SAFE)
# ==================================================

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
