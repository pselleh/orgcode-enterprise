from tutor import hooks

# Mount local source directory into Docker build context
hooks.Filters.IMAGES_BUILD_MOUNTS.add_item(
    (
        "openedx",
        "/home/cbaadmin/src/orgcode-enterprise",
        "/mnt/orgcode-enterprise",
    )
)

# Install the package into the openedx image
hooks.Filters.IMAGES_BUILD.add_item(
    (
        "openedx",
        """
        RUN uv pip install -e /mnt/orgcode-enterprise
        """,
    )
)
