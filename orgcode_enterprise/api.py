import logging
from django.core.exceptions import ImproperlyConfigured
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from orgcode_enterprise.services import (
    GENERIC_INVALID_MESSAGE,
    InvalidOrgCode,
    active_grants_for_user,
    authorize_private_product,
    redeem_org_code,
    serialize_grant,
)


logger = logging.getLogger(__name__)
class OrgCodeScopedRateThrottle(ScopedRateThrottle):
    """Use configured rates while retaining secure defaults."""

    DEFAULT_RATES = {
        "orgcode_redeem": "10/hour",
        "orgcode_access": "600/hour",
        "orgcode_authorize": "120/hour",
    }

    def get_rate(self):
        configured_rate = self.THROTTLE_RATES.get(self.scope)
        if configured_rate:
            return configured_rate

        default_rate = self.DEFAULT_RATES.get(self.scope)
        if default_rate:
            return default_rate

        raise ImproperlyConfigured(
            f"No throttle rate configured for organization-code scope {self.scope!r}."
        )

class RedeemOrgCodeView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (OrgCodeScopedRateThrottle,)
    throttle_scope = "orgcode_redeem"

    def post(self, request):
        raw_code = request.data.get("code")
        if not raw_code:
            return Response({"error": GENERIC_INVALID_MESSAGE}, status=status.HTTP_400_BAD_REQUEST)
        try:
            grant, created = redeem_org_code(request.user, raw_code)
        except InvalidOrgCode:
            return Response({"error": GENERIC_INVALID_MESSAGE}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:  # noqa: BLE001 - log internally without exposing code or internals
            logger.exception("Organization-code redemption failed for user_id=%s", request.user.id)
            return Response(
                {"error": "Organization access could not be applied."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            {
                "message": "Organization access applied.",
                "created": created,
                "grant": serialize_grant(grant),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class CurrentAccessView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (OrgCodeScopedRateThrottle,)
    throttle_scope = "orgcode_access"

    def get(self, request):
        grants = [serialize_grant(grant) for grant in active_grants_for_user(request.user)]
        return Response({"public_catalog_access": True, "organization_grants": grants})


class AuthorizeProductView(APIView):
    """Re-check a private product immediately before checkout or enrollment."""

    permission_classes = (IsAuthenticated,)
    throttle_classes = (OrgCodeScopedRateThrottle,)
    throttle_scope = "orgcode_authorize"

    def post(self, request):
        policy_key = request.data.get("access_policy_key", "")
        product_type = request.data.get("product_type", "")
        product_key = request.data.get("product_key", "")
        if not policy_key or not product_key or product_type not in {"course", "program"}:
            return Response({"authorized": False}, status=status.HTTP_400_BAD_REQUEST)

        grant = authorize_private_product(
            request.user,
            access_policy_key=policy_key,
            product_type=product_type,
            product_key=product_key,
        )
        if not grant:
            return Response({"authorized": False}, status=status.HTTP_403_FORBIDDEN)
        return Response({"authorized": True, "grant": serialize_grant(grant)})
