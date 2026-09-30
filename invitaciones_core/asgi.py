"""
ASGI config for invitaciones_core project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# Un servidor web real (gunicorn, uWSGI) entra por aquí: por defecto usa la
# configuración de producción. runserver no pasa por esta línea (manage.py
# ya fijó settings de desarrollo), así que en tu compu no cambia nada.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invitaciones_core.settings_produccion')

application = get_asgi_application()
