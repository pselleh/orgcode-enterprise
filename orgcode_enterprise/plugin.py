from tutor import hooks

# Install the Django app into the Open edX image (container Python)
hooks.Filters.CONFIG_DEFAULTS.add_item(
    (
        "OPENEDX_EXTRA_PIP_REQUIREMENTS",
        [
            "git+https://github.com/pselleh/orgcode-enterprise.git@main",
        ],
    )
)

# ✅ DO NOT patch lms-env INSTALLED_APPS (it can wipe core Django apps).
# Instead, patch the Django settings so we append safely.

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-lms-production-settings",
        """
# --- orgcode_enterprise: add Django app safely ---
if "orgcode_enterprise" not in INSTALLED_APPS:
    INSTALLED_APPS.append("orgcode_enterprise")
""",
    )
)

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-lms-development-settings",
        """
# --- orgcode_enterprise: add Django app safely ---
if "orgcode_enterprise" not in INSTALLED_APPS:
    INSTALLED_APPS.append("orgcode_enterprise")
""",
    )
)
