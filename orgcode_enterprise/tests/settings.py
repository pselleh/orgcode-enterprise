SECRET_KEY = "orgcode-enterprise-tests"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "rest_framework",
    "orgcode_enterprise",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

ROOT_URLCONF = "orgcode_enterprise.tests.urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True

REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_RATES": {
        "orgcode_redeem": "100/minute",
        "orgcode_access": "100/minute",
        "orgcode_authorize": "100/minute",
    }
}
