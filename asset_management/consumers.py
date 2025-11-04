import json
from channels.generic.websocket import AsyncWebsocketConsumer


class AssetPriceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("asset_price", self.channel_name)
        await self.accept()

        from .models import PlatformOptions
        from .tasks import broadcast_asset_price

        try:
            platform_options = await PlatformOptions.objects.aget(id=1)
            print(platform_options.gold_appreciation)
            await broadcast_asset_price(
                {
                    "gold_appreciation": float(platform_options.gold_appreciation),
                    "silver_appreciation": float(platform_options.silver_appreciation),
                }
            )
        except Exception as e:
            print("error first time sending data via socket>> ", e)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("asset_price", self.channel_name)

    async def asset_price_update(self, event):

        payload = {
            "gold_buy_price": event["gold_buy_price"],
            "silver_buy_price": event["silver_buy_price"],
            "gold_sell_price": event["gold_sell_price"],
            "silver_sell_price": event["silver_sell_price"],
        }

        if "gold_appreciation" in event:
            payload["gold_appreciation"] = event["gold_appreciation"]

        if "silver_appreciation" in event:
            payload["silver_appreciation"] = event["silver_appreciation"]

        await self.send(text_data=json.dumps(payload))
