from tutor import hooks

# =========================================================
# COPY PACKAGE INTO IMAGE
# =========================================================

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-dockerfile-post-python-requirements",
        """
COPY ./plugins/orgcode-enterprise /openedx/plugins/orgcode-enterprise
RUN pip install -e /openedx/plugins/orgcode-enterprise
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
