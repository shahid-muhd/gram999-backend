from django.shortcuts import render

# views.py
from rest_framework import generics, permissions
from .models import PlatformOptions
from .serializers import PlatformOptionsSerializer
from .models import AssetTransaction
from .serializers import AssetTransactionSerializer

class PlatformOptionsUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = PlatformOptionsSerializer

    def get_object(self):
        return PlatformOptions.objects.get(id=1)

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