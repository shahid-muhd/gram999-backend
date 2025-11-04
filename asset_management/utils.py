import random
from payments.models import AssetType
from decimal import Decimal, ROUND_HALF_UP
from django.core.cache import cache
from .models import PlatformOptions

from decimal import Decimal
from asgiref.sync import async_to_sync


def get_price_per_gram(asset_type: str) -> dict[str, Decimal]:
    """
    Calls async `calculate_metal_prices()` and returns buy/sell prices
    for the given asset type (GOLD or SILVER).
    """

    result = async_to_sync(calculate_metal_prices)()

    # result should be a dict containing:
    # gold_buy_price, gold_sell_price, silver_buy_price, silver_sell_price

    if not isinstance(result, dict):
        raise ValueError("calculate_metal_prices() did not return a dict")

    if asset_type == AssetType.GOLD:
        return {
            "buy": result["gold_buy_price"],
            "sell": result["gold_sell_price"],
        }

    elif asset_type == AssetType.SILVER:
        return {
            "buy": result["silver_buy_price"],
            "sell": result["silver_sell_price"],
        }

    raise ValueError(f"Unknown asset type: {asset_type}")


def quantize_amount(d: Decimal, places: int = 4) -> Decimal:
    """
    Quantizes a Decimal value to the given number of decimal places.
    Defaults to 4 places, using standard rounding (half up).
    """
    quantizer = Decimal(f"1e-{places}")
    return d.quantize(quantizer, rounding=ROUND_HALF_UP)


import httpx


EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


async def send_push_notification(tokens, title, body):
    async with httpx.AsyncClient() as client:
        for token in tokens:
            message = {
                "to": token,
                "sound": "default",
                "title": title,
                "body": body,
            }
            await client.post(EXPO_PUSH_URL, json=message)
            print("<<<notification triggered>>>")


async def calculate_metal_prices():

    gold_spot_price = cache.get("gold_buy_price_aed", Decimal("320.51"))
    silver_spot_price = cache.get("silver_buy_price_aed", Decimal("5.21"))
    # Initialize prices
    gold_buy_price = Decimal(gold_spot_price)
    silver_buy_price = Decimal(silver_spot_price)
    gold_sell_price = Decimal(gold_spot_price)
    silver_sell_price = Decimal(silver_spot_price)

    # Fetch platform margins
    platform_options = await PlatformOptions.objects.aget(id=1)

    if platform_options:
        gold_margin = Decimal(platform_options.gold_margin or 0) / Decimal("100")
        silver_margin = Decimal(platform_options.silver_margin or 0) / Decimal("100")
        gold_markdown = Decimal(platform_options.gold_markdown or 0) / Decimal("100")
        silver_markdown = Decimal(platform_options.silver_markdown or 0) / Decimal(
            "100"
        )

        # Apply margins and markdowns
        gold_buy_price += gold_margin * gold_spot_price
        silver_buy_price += silver_margin * silver_spot_price

        gold_sell_price -= gold_markdown * gold_spot_price
        silver_sell_price -= silver_markdown * silver_spot_price

    # Round final values
    return {
        "gold_buy_price": quantize_amount(gold_buy_price,2),
        "silver_buy_price": quantize_amount(silver_buy_price,2),
        "gold_sell_price": quantize_amount(gold_sell_price,2),
        "silver_sell_price": quantize_amount(silver_sell_price,2),
    }
