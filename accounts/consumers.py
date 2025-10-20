import json
from channels.generic.websocket import AsyncWebsocketConsumer
from urllib.parse import parse_qs

class AccountConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query_params = parse_qs(self.scope["query_string"].decode())
        user_id = query_params.get("user_id", [None])[0]

        if not user_id:
            await self.close()
            return

        # Create a group name specific to this user
        self.group_name = f"user_{user_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.send(
            text_data=json.dumps({
                "type": "connection_established",
                "message": f"Connected to account channel for user {user_id}"
            })
        )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle messages from the client if needed."""
        data = json.loads(text_data)
        if data.get("action") == "ping":
            await self.send(text_data=json.dumps({"pong": True}))

    async def account_update(self, event):
        """Send updates to the connected user."""
        await self.send(text_data=json.dumps(event["data"]))
