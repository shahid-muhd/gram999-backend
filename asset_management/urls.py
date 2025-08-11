# urls.py
from django.urls import path
from .views import PlatformOptionsUpdateView

urlpatterns = [
    path("platform-options/", PlatformOptionsUpdateView.as_view(), name="platform-options-update"),
    # path("buy-assets/", PlatformOptionsUpdateView.as_view(), name="platform-options-update"),
    # path("sell-assets/", PlatformOptionsUpdateView.as_view(), name="platform-options-update"),
]
