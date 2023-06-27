from megedc import __version__
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class VersionAPIView(APIView):

    permission_classes = []

    def get(self, request, *args, **kwargs):
        data = {
            'name': 'Mege Data Collector',
            'ver': __version__
        }
        return Response(data, status=status.HTTP_200_OK)
