from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from orgcode_enterprise.models import OrgCode


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def apply_org_code(request):
    code_value = request.data.get("code")

    if not code_value:
        return Response({"error": "Code is required"}, status=400)

    try:
        org_code = OrgCode.objects.get(code=code_value)
    except OrgCode.DoesNotExist:
        return Response({"error": "Invalid code"}, status=404)

    valid, message = org_code.apply_to_user(request.user)

    if not valid:
        return Response({"error": message}, status=400)

    return Response({"message": message})
