from tutor import hooks

# Install package from GitHub
hooks.Filters.CONFIG_DEFAULTS.add_item(
    (
        "OPENEDX_EXTRA_PIP_REQUIREMENTS",
        [
            "git+https://github.com/pselleh/orgcode-enterprise.git@main"
        ],
    )
)

# Proper YAML patch for LMS (Ulmo-safe)
hooks.Filters.ENV_PATCHES.add_item((
    "lms-env",
    """
INSTALLED_APPS:
  - orgcode_enterprise
"""
))
