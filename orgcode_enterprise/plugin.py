from tutor import hooks

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-dockerfile-post-python-requirements",
        """
RUN pip install "git+https://github.com/pselleh/orgcode-enterprise.git@v1.1.1#egg=tutor-orgcode-enterprise"
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

REST_FRAMEWORK.setdefault("DEFAULT_THROTTLE_RATES", {})
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].setdefault("orgcode_redeem", "10/hour")
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].setdefault("orgcode_access", "600/hour")
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].setdefault("orgcode_authorize", "120/hour")
""",
        ),
        (
            "openedx-lms-development-settings",
            """
ORGCODE_ENTERPRISE_APP = "orgcode_enterprise.app_config.OrgcodeEnterpriseConfig"

if ORGCODE_ENTERPRISE_APP not in INSTALLED_APPS:
    INSTALLED_APPS.append(ORGCODE_ENTERPRISE_APP)

REST_FRAMEWORK.setdefault("DEFAULT_THROTTLE_RATES", {})
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].setdefault("orgcode_redeem", "100/hour")
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].setdefault("orgcode_access", "6000/hour")
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].setdefault("orgcode_authorize", "1000/hour")
""",
        ),
    ]
)
