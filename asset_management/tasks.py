import random
import httpx
from decimal import Decimal
from asgiref.sync import async_to_sync, sync_to_async
from channels.layers import get_channel_layer
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from payments.models import SipPlan
from .services import run_sip_plan
from .utils import calculate_metal_prices

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


# ---------------------------------------------
#  Async function for broadcasting live prices
# ---------------------------------------------
async def broadcast_asset_price(asset_projection={}):
    try:
        from .models import PlatformOptions, PriceAlert, PushToken

        prices = await calculate_metal_prices()
        prices = {k: float(v) for k, v in prices.items()}

        print("prices>>>", prices)
        # WebSocket broadcast
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            "asset_price",
            {
                "type": "asset_price_update",
                # "gold_buy_price": float(gold_buy_price),
                # "silver_buy_price": float(silver_buy_price),
                # "gold_sell_price": float(gold_sell_price),
                # "silver_sell_price": float(silver_sell_price),
                **prices,
                **asset_projection,
            },
        )

        print("✅ broadcasted asset price >>>", prices)

        # Check price alerts
        alerts = await sync_to_async(list)(
            PriceAlert.objects.filter(is_triggered=False)
        )

        for alert in alerts:
            current_price = (
                prices["gold_buy_price"]
                if alert.asset == "gold"
                else prices["silver_buy_price"]
            )

            if (alert.condition == "above" and current_price > alert.target_price) or (
                alert.condition == "below" and current_price < alert.target_price
            ):
                tokens = await sync_to_async(
                    lambda: list(
                        PushToken.objects.filter(user=alert.user).values_list(
                            "token", flat=True
                        )
                    )
                )()
                print("📈 Price reached trigger point")

                async with httpx.AsyncClient() as client:
                    for token in tokens:
                        message = {
                            "to": token,
                            "sound": "default",
                            "title": f"{alert.asset.capitalize()} Alert",
                            "body": f"{alert.asset.capitalize()} price is now {current_price}",
                        }
                        await client.post(EXPO_PUSH_URL, json=message)
                        print("📲 Push notification sent")

                # alert.is_triggered = True
                # await sync_to_async(lambda: alert.save())()
                await sync_to_async(alert.delete)()
    except Exception as e:
        print(f"❌ Error broadcasting asset price: {e}")


# ---------------------------------------------
#  Celery task wrapper for broadcasting
# ---------------------------------------------
@shared_task
def broadcast_asset_price_task():
    """Celery wrapper for async broadcast"""
    async_to_sync(broadcast_asset_price)()


# ---------------------------------------------
#  SIP daily execution task
# ---------------------------------------------
@shared_task
def run_due_sips():
    """Run all SIPs that are due today"""
    today = timezone.now().date()
    sips = SipPlan.objects.filter(is_active=True, next_run__lte=today)

    for sip in sips:
        try:
            run_sip_plan(sip)
        except Exception as e:
            print(f"❌ SIP execution failed for {sip.id}: {e}")


# ---------------------------------------------
#  Update metal prices every minute
# ---------------------------------------------
@shared_task
def update_metal_prices():
    """Fetch latest gold/silver prices from MetalPriceAPI and store in cache"""
    API_URL = "https://api.metalpriceapi.com/v1/latest"
    API_KEY = settings.METALPRICE_API_KEY
    BASE_CURRENCY = "USD"
    TARGET_CURRENCY = "AED"

    try:
        response = httpx.get(
            API_URL,
            params={
                "api_key": API_KEY,
                "base": BASE_CURRENCY,
                "currencies": f"XAU,XAG,{TARGET_CURRENCY}",
            },
            timeout=10,
        )
        data = response.json()

        if not data.get("success"):
            raise ValueError(f"API error: {data}")

        rates = data["rates"]
        usd_to_aed = Decimal(str(rates.get(TARGET_CURRENCY)))

        gold_per_gram = (
            Decimal(str(rates["USDXAU"])) / Decimal("31.1035")
        ) * usd_to_aed
        silver_per_gram = (
            Decimal(str(rates["USDXAG"])) / Decimal("31.1035")
        ) * usd_to_aed

        cache.set(
            "gold_buy_price_aed", gold_per_gram.quantize(Decimal("0.01")), timeout=120
        )
        cache.set(
            "silver_buy_price_aed",
            silver_per_gram.quantize(Decimal("0.01")),
            timeout=120,
        )

        print(
            f"💰 Updated metal prices → Gold: {gold_per_gram:.2f}, Silver: {silver_per_gram:.2f}"
        )

        # Immediately broadcast after update (so data is fresh)
        async_to_sync(broadcast_asset_price)()

    except Exception as e:
        print(f"❌ Error updating metal prices: {e}")
