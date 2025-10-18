import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
import asset_management.routing


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gram999_backend.settings')




application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            asset_management.routing.websocket_urlpatterns
        )
    ),
})


