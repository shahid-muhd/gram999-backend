from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path("gold-price/", consumers.GoldPriceConsumer.as_asgi()),
]
