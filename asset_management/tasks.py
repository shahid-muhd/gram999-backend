import random
import httpx
import json
from apscheduler.schedulers.background import BackgroundScheduler
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync, sync_to_async

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


async def broadcast_asset_price(asset_projection={}):
    try:
        gold_price = round(random.uniform(320, 410), 2)
        silver_price = round(random.uniform(210, 300), 2)

        from .models import PlatformOptions, PriceAlert, PushToken

        # async ORM (aget is supported)
        platform_options = await PlatformOptions.objects.aget(id=1)

        if platform_options:
            gold_price += (float(platform_options.gold_margin or 0) / 100) * gold_price
            silver_price += (float(platform_options.silver_margin or 0) / 100) * silver_price

        gold_price = round(gold_price, 3)
        silver_price = round(silver_price, 3)

        # Websocket broadcast
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            "asset_price",
            {
                "type": "asset_price_update",
                "gold_price": float(gold_price),
                "silver_price": float(silver_price),
                **asset_projection,
            },
        )
        #  ORM: wrap sync calls with sync_to_async
        alerts = await sync_to_async(list)(
            PriceAlert.objects.filter(is_triggered=False)
        )

        for alert in alerts:
            current_price = gold_price if alert.asset == "gold" else silver_price

            if (alert.condition == "above" and current_price > alert.target_price) or (
                alert.condition == "below" and current_price < alert.target_price
            ):
                #  get tokens
                tokens = await sync_to_async(list)(
                    PushToken.objects.filter(user=alert.user).values_list("token", flat=True)
                )

                async with httpx.AsyncClient() as client:
                    for token in tokens:
                        message = {
                            "to": token,
                            "sound": "default",
                            "title": f"{alert.asset.capitalize()} Alert",
                            "body": f"{alert.asset.capitalize()} price is now {current_price}",
                        }
                        await client.post(EXPO_PUSH_URL, json=message)

                #  save alert safely
                alert.is_triggered = True
                await sync_to_async(alert.save)()

    except Exception as e:
        print(f"❌ Error broadcasting asset price: {e}")


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(async_to_sync(broadcast_asset_price), "interval", minutes=1)
    scheduler.start()
