from tutor import hooks

# Add Django app to LMS
hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-lms-common-settings",
        """
INSTALLED_APPS.append("orgcode_enterprise")
"""
    )
)

