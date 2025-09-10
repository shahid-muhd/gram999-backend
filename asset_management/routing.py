from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path("asset-price/", consumers.AssetPriceConsumer.as_asgi()),
]
