from importlib import import_module

from django.urls import include, path


openedx_lms_urls = import_module("lms.urls")

urlpatterns = [
    path("api/orgcode/", include("orgcode_enterprise.urls")),
]

urlpatterns += openedx_lms_urls.urlpatterns
