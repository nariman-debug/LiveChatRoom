"""
ASGI config for LiveChatRoom project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application

# تنظیم متغیر محیطی باید در بالاترین نقطه انجام شود
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LiveChatRoom.settings')

# بارگذاری application جنگو
django_asgi_app = get_asgi_application()

# حالا ماژول‌های وابسته به جنگو را import کنید
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import chatroom.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            chatroom.routing.websocket_urlpatterns
        )
    ),
})
