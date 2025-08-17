# urls.py
from django.urls import path
from .views import PlatformOptionsRetrieveUpdateView

urlpatterns = [
    path("platform-settings/", PlatformOptionsRetrieveUpdateView.as_view(), name="platform-options-update"),
    # path("buy-assets/", PlatformOptionsUpdateView.as_view(), name="platform-options-update"),
    # path("sell-assets/", PlatformOptionsUpdateView.as_view(), name="platform-options-update"),
]
