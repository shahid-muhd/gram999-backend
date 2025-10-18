import random
from payments.models import AssetType
from decimal import Decimal, ROUND_DOWN


def get_price_per_gram(asset_type: str) -> Decimal:
    if asset_type == AssetType.GOLD:

        # return round(random.uniform(320, 410), 2)
        return 320
    if asset_type == AssetType.SILVER:
        # return round(random.uniform(210, 300), 2)
        return 210
    raise ValueError("unknown asset")


def quantize_amount(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.0001"), rounding=ROUND_DOWN)




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
