from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(["POST"])
def apply(request):
    code = request.data.get("code")

    if not code:
        return Response({"error": "code is required"}, status=400)

    return Response({"received_code": code})
