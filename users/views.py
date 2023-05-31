from rest_framework import status
from rest_framework.generics import GenericAPIView, RetrieveAPIView
from rest_framework.response import Response

from users.serializers import UserSerializer


class SimpleHelloWorld(RetrieveAPIView, GenericAPIView):
    serializer_class = UserSerializer

    def retrieve(self, request, *args, **kwargs):
        return Response({'answer': 'hello world'}, status=status.HTTP_200_OK)
