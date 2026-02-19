from setuptools import setup, find_packages

setup(
    name="tutor-orgcode-enterprise",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["tutor>=21.0.0"],
    entry_points={
        "tutor.plugin.v1": [
            "orgcode_enterprise = orgcode_enterprise.plugin"
        ]
    },
)
