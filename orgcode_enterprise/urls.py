from django.urls import path

from orgcode_enterprise.api import AuthorizeProductView, CurrentAccessView, RedeemOrgCodeView

urlpatterns = [
    # Backward-compatible path used by the current registration client.
    path("apply/", RedeemOrgCodeView.as_view(), name="orgcode-apply-legacy"),
    path("v1/redeem/", RedeemOrgCodeView.as_view(), name="orgcode-redeem"),
    path("v1/access/", CurrentAccessView.as_view(), name="orgcode-current-access"),
    path("v1/authorize/", AuthorizeProductView.as_view(), name="orgcode-authorize-product"),
]
