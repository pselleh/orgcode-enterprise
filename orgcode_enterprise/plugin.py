from tutor import hooks

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-dockerfile-post-python-requirements",
        """
RUN pip install -e git+https://github.com/pselleh/orgcode-enterprise.git#egg=tutor-orgcode-enterprise
""",
    )
)

hooks.Filters.ENV_PATCHES.add_items(
    [
        (
            "openedx-lms-production-settings",
            """
ORGCODE_ENTERPRISE_APP = "orgcode_enterprise.app_config.OrgcodeEnterpriseConfig"

if ORGCODE_ENTERPRISE_APP not in INSTALLED_APPS:
    INSTALLED_APPS.append(ORGCODE_ENTERPRISE_APP)
""",
        ),
        (
            "openedx-lms-development-settings",
            """
ORGCODE_ENTERPRISE_APP = "orgcode_enterprise.app_config.OrgcodeEnterpriseConfig"

if ORGCODE_ENTERPRISE_APP not in INSTALLED_APPS:
    INSTALLED_APPS.append(ORGCODE_ENTERPRISE_APP)
""",
        ),
    ]
)
