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
# REGISTER REAL DJANGO APP
# =========================================================

hooks.Filters.ENV_PATCHES.add_items(
    [
        (
            "openedx-lms-production-settings",
            """
if "orgcode_enterprise.apps.orgcode" not in INSTALLED_APPS:
    INSTALLED_APPS.append("orgcode_enterprise.apps.orgcode")
""",
        ),
        (
            "openedx-lms-development-settings",
            """
if "orgcode_enterprise.apps.orgcode" not in INSTALLED_APPS:
    INSTALLED_APPS.append("orgcode_enterprise.apps.orgcode")
""",
        ),
    ]
)
