from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from django.db import transaction
import logging

from orgcode_enterprise.models import OrgCode

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def apply_org_code(request):
    """
    Apply an organization code to the authenticated user.

    Expected payload:
    {
        "code": "ABC123"
    }
    """
    user = request.user

    code_value = request.data.get("code")

    if not code_value:
        return Response(
            {"error": "Code is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        org_code = OrgCode.objects.get(code=code_value)
    except OrgCode.DoesNotExist:
        return Response(
            {"error": "Invalid code"},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        with transaction.atomic():
            valid, message = org_code.apply_to_user(user)

            if not valid:
                return Response(
                    {"error": message},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {"message": message},
                status=status.HTTP_200_OK,
            )

    except Exception as e:
        logger.exception("Error applying org code")

        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
