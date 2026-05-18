from tutor import hooks

# =========================================================
# INSTALL PACKAGE INTO OPENEDX IMAGE
# =========================================================

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-dockerfile-post-python-requirements",
        """
RUN pip install -e git+https://github.com/pselleh/orgcode-enterprise.git#egg=tutor-orgcode-enterprise
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
