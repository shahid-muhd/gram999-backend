import requests
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def fetch_gold_price_and_broadcast():

    api_key = "goldapi-8vd7smdmydrz4-io"
    symbol = "XAU"
    curr = "USD"
    date = "/20250731"

    url = f"https://www.goldapi.io/api/{symbol}/{curr}{date}"

    headers = {"x-access-token": api_key, "Content-Type": "application/json"}

    try:
        # Replace this URL with your real gold price API
        # response = requests.get(url, headers=headers)
        # response.raise_for_status()

        # data = response.json()
        # gold_price = data.get("price")  
        import random
        gold_price = round(random.uniform(310, 400), 2)         

        # Broadcast to group
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "gold_prices",
            {
                "type": "gold_price_update",
                "price": gold_price,
            },
        )

        print(f"✅ Broadcasted gold price: {gold_price}")

    except Exception as e:
        pass
        # print(f"❌ Error fetching gold price: {e}")
