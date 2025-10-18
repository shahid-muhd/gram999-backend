# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PlatformOptionsRetrieveUpdateView,
    PriceAlertViewSet,
    PushTokenViewSet,
    BalanceViewSet,
    BuyAssetView,
    SellAssetView,
    SipPlanViewSet,
    GoldLeaseViewSet,
    LeasePayoutViewSet
)

router = DefaultRouter()
router.register(r"alerts", PriceAlertViewSet, basename="pricealert")
router.register(r"push-tokens", PushTokenViewSet, basename="pushtoken")
router.register(r"balance", BalanceViewSet, basename="balance")
router.register(r"sips", SipPlanViewSet, basename="sipplan")
router.register(r"leases", GoldLeaseViewSet, basename="goldlease")
router.register(r"lease-payouts", LeasePayoutViewSet, basename="leasepayout")

urlpatterns = [
    path(
        "platform-settings/",
        PlatformOptionsRetrieveUpdateView.as_view(),
        name="platform-options-update",
    ),
    path(
        "buy-asset/",
        BuyAssetView.as_view(),
        name="buy-asset",
    ),
    path(
        "sell-asset/",
        SellAssetView.as_view(),
        name="sell-asset",
    ),
    path("", include(router.urls)),
]
