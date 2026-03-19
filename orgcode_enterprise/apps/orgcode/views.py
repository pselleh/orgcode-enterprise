from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(["POST"])
def apply(request):
    code = request.data.get("code")
    return Response({"received_code": code})
