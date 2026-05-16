from tutor import hooks

# ==================================================
# INSTALL orgcode_enterprise INTO OPENEDX IMAGE
# ==================================================

hooks.Filters.ENV_PATCHES.add_item(
    (
        "private.txt",
        """
-e /openedx/orgcode-enterprise
""",
    )
)

# ==================================================
# MOUNT PACKAGE INTO OPENEDX BUILD CONTEXT
# ==================================================

hooks.Filters.MOUNTED_DIRECTORIES.add_item(
    (
        "openedx",
        "/home/cbaadmin/src/orgcode-enterprise",
        "/openedx/orgcode-enterprise",
    )
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
# REGISTER URLS SAFELY
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
