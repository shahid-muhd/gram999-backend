from django.urls import path
from .views import UserListCreateView, UserDetailView
from rest_framework_simplejwt.views import TokenRefreshView
from .views import CustomTokenObtainPairView
from .views import (
    start_kyc_verification,
    VerificationAPIView,
    shufti_callback,
    kyc_redirect,
)

urlpatterns = [
    path("token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("users/", UserListCreateView.as_view(), name="user-list-create"),
    path("users/<int:id>/", UserDetailView.as_view(), name="user-detail"),
    path("verify/", VerificationAPIView.as_view(), name="verification"),
    path("kyc/verify/", start_kyc_verification, name="start_verification"),
    path("kyc/callback/", shufti_callback, name="shufti_callback"),
    path("kyc/redirect/", kyc_redirect, name="shufti_redirect"),
]
