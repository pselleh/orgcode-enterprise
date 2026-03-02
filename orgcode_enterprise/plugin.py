from tutor import hooks

hooks.Filters.CONFIG_DEFAULTS.add_item(
    (
        "OPENEDX_EXTRA_PIP_REQUIREMENTS",
        [
            "-e ./plugins/orgcode-enterprise"
        ],
    )
)
