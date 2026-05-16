from setuptools import setup, find_packages

setup(
    name="tutor-orgcode-enterprise",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        "tutor.plugin.v1": [
            "orgcode_enterprise = orgcode_enterprise.plugin"
        ]
    },
)
