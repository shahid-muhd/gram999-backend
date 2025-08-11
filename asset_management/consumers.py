import json
from channels.generic.websocket import AsyncWebsocketConsumer

class GoldPriceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("gold_prices", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("gold_prices", self.channel_name)

    async def gold_price_update(self, event):
        await self.send(text_data=json.dumps({
            "price": event["price"]
        }))
                                                                                                                