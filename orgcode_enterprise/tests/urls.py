from django.urls import include, path

from orgcode_enterprise import urls as orgcode_urls


urlpatterns = [
    path(
        "api/orgcode/",
        include(
            (orgcode_urls.urlpatterns, "orgcode_enterprise"),
            namespace="orgcode_enterprise",
        ),
    ),
]
