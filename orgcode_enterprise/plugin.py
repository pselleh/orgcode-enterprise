from tutor import hooks

# =========================================================
# MOUNT PACKAGE INTO OPENEDX CONTAINER
# =========================================================

hooks.Filters.MOUNTED_DIRECTORIES.add_item(
    (
        "openedx",
        "/home/cbaadmin/src/orgcode-enterprise",
        "/openedx/requirements/orgcode-enterprise",
    )
)

# =========================================================
# PATCH OPENEDX DOCKERFILE
# =========================================================

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-dockerfile-post-python-requirements",
        """
RUN pip install -e /openedx/requirements/orgcode-enterprise
""",
    )
)

# =========================================================
# REGISTER DJANGO APP
# =========================================================

hooks.Filters.ENV_PATCHES.add_items(
    [
        (
            "openedx-lms-production-settings",
            '''
if "orgcode_enterprise" not in INSTALLED_APPS:
    INSTALLED_APPS.append("orgcode_enterprise")
''',
        ),
        (
            "openedx-lms-development-settings",
            '''
if "orgcode_enterprise" not in INSTALLED_APPS:
    INSTALLED_APPS.append("orgcode_enterprise")
''',
        ),
    ]
)

# =========================================================
# REGISTER URLS
# =========================================================

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-lms-common-settings",
        '''
try:
    from django.urls import include, path

    if "urlpatterns" in globals():
        urlpatterns += [
            path("api/orgcode/", include("orgcode_enterprise.urls")),
        ]
except Exception:
    pass
''',
    )
)
