from .models import PriceAlert
from django.shortcuts import render
from rest_framework import serializers, viewsets
from .models import PriceAlert
# views.py
from rest_framework import generics, permissions ,status
from .models import PlatformOptions
from .serializers import PlatformOptionsSerializer
from .models import AssetTransaction
from .serializers import AssetTransactionSerializer , PriceAlertSerializer ,PushTokenSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
class PlatformOptionsRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = PlatformOptionsSerializer

    def get_object(self):
        obj, created = PlatformOptions.objects.get_or_create(id=1)
        return obj

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            # Allow any authenticated user to read (GET, HEAD, OPTIONS)
            permission_classes = [permissions.IsAuthenticated]
        else:
            # Allow only admin users to update
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]


class AssetTransactionCreateUpdateView(generics.CreateAPIView, generics.UpdateAPIView):
    """
    Allows creating and updating asset transactions.
    Ledger is automatically updated via signals.
    """

    queryset = AssetTransaction.objects.all()
    serializer_class = AssetTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)

class PriceAlertViewSet(viewsets.ModelViewSet):
    serializer_class = PriceAlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PriceAlert.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


from .models import PushToken

class PushTokenViewSet(viewsets.ModelViewSet):
    serializer_class = PushTokenSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PushToken.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)