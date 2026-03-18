from django.urls import path
from .api import apply_org_code

urlpatterns = [
    path("apply/", apply_org_code, name="apply_org_code"),
]
