from django.urls import path
from .views import UserListCreateView, UserDetailView
from rest_framework_simplejwt.views import TokenRefreshView
from .views import CustomTokenObtainPairView
from .views import (
    start_kyc_verification,
    VerificationAPIView,
    kyc_callback,
    kyc_redirect,
    NomineeView,
    toggle_user_block
)


from .views import AddressListCreateView, AddressRetrieveUpdateDestroyView


urlpatterns = [
    path("token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("users/", UserListCreateView.as_view(), name="user-list-create"),
    path("users/<int:id>/", UserDetailView.as_view(), name="user-detail"),
    path("users/<int:user_id>/toggle-block/", toggle_user_block, name="toggle_user_block"),
    path("verify/", VerificationAPIView.as_view(), name="verification"),
    path("kyc/verify/", start_kyc_verification, name="start_verification"),
    path("kyc/callback/", kyc_callback, name="kyc_callback"),
    path("kyc/redirect/", kyc_redirect, name="shufti_redirect"),
    path("nominee/", NomineeView.as_view(), name="nominee"),
    path("addresses/", AddressListCreateView.as_view(), name="address-list-create"),
    path(
        "addresses/<int:pk>/",
        AddressRetrieveUpdateDestroyView.as_view(),
        name="address-detail",
    ),
]
