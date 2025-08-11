from django.urls import path
from .views import UserListCreateView, UserDetailView
from rest_framework_simplejwt.views import TokenRefreshView
from .views import CustomTokenObtainPairView
from accounts.views import VerificationAPIView

urlpatterns = [
    path("token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("users/", UserListCreateView.as_view(), name="user-list-create"),
    path("users/<int:id>/", UserDetailView.as_view(), name="user-detail"),
    path("verify/", VerificationAPIView.as_view(), name="verification"),
]
