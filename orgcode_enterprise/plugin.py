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
# REGISTER APP
# =========================================================

hooks.Filters.ENV_PATCHES.add_items(
    [
        (
            "openedx-lms-production-settings",
            """
if "orgcode_enterprise.apps.OrgcodeEnterpriseConfig" not in INSTALLED_APPS:
    INSTALLED_APPS.append("orgcode_enterprise.apps.OrgcodeEnterpriseConfig")
""",
        ),
        (
            "openedx-lms-development-settings",
            """
if "orgcode_enterprise.apps.OrgcodeEnterpriseConfig" not in INSTALLED_APPS:
    INSTALLED_APPS.append("orgcode_enterprise.apps.OrgcodeEnterpriseConfig")
""",
        ),
    ]
)

# =========================================================
# PATCH LMS URLCONF DIRECTLY
# =========================================================

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-lms-urls",
        """
from django.urls import include, path

urlpatterns.append(
    path("api/orgcode/", include("orgcode_enterprise.urls"))
)
""",
    )
)
