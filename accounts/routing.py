from django.urls import path
from accounts.consumers import AccountConsumer

websocket_urlpatterns = [
    path("account-status/", AccountConsumer.as_asgi()),
]
