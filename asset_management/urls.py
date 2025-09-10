# urls.py
from django.urls import path, include
from .views import PlatformOptionsRetrieveUpdateView
from rest_framework.routers import DefaultRouter
from .views import (
    PlatformOptionsRetrieveUpdateView,
    PriceAlertViewSet,
    PushTokenViewSet,
)

router = DefaultRouter()
router.register(r"alerts", PriceAlertViewSet, basename="pricealert")
router.register(r"push-tokens", PushTokenViewSet, basename="pushtoken")


urlpatterns = [
    path(
        "platform-settings/",
        PlatformOptionsRetrieveUpdateView.as_view(),
        name="platform-options-update",
    ),
    path("", include(router.urls)),
    # path("buy-assets/", PlatformOptionsUpdateView.as_view(), name="platform-options-update"),
    # path("sell-assets/", PlatformOptionsUpdateView.as_view(), name="platform-options-update"),
]
