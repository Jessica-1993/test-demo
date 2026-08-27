import os

from django.core.asgi import get_asgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

django_asgi_app = get_asgi_application()

try:
    from channels.routing import ProtocolTypeRouter

    application = ProtocolTypeRouter({
        "http": django_asgi_app,
    })
except ImportError:
    application = django_asgi_app
