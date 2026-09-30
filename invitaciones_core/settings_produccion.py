"""
Settings de PRODUCCIÓN (el servidor real). Importa todo lo de settings.py
y cambia lo que no puede quedarse como en tu compu.

Los secretos NO viven en el código: se leen del archivo .env que existe
solo en el servidor (ver .env.ejemplo y DESPLIEGUE.md). Si falta uno
obligatorio, Django se niega a arrancar con un mensaje claro, en vez de
arrancar inseguro.
"""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# El .env se carga ANTES de importar settings.py: ese archivo también lee
# variables (datos del aviso de privacidad) y tienen que existir ya.
try:
    from dotenv import load_dotenv
    # DJANGO_ARCHIVO_ENV permite apuntar a otro archivo (lo usan las pruebas)
    load_dotenv(os.environ.get('DJANGO_ARCHIVO_ENV', Path(__file__).resolve().parent.parent / '.env'))
except ImportError:
    pass   # sin python-dotenv, las variables pueden venir del sistema

from .settings import *  # noqa: E402,F401,F403
from .settings import BASE_DIR, MIDDLEWARE  # noqa: E402


def _obligatoria(nombre):
    valor = os.environ.get(nombre, '').strip()
    if not valor:
        raise ImproperlyConfigured(
            f'Falta la variable {nombre} en el archivo .env del servidor (ver .env.ejemplo).'
        )
    return valor


def _si_no(nombre, por_defecto):
    return os.environ.get(nombre, '1' if por_defecto else '0').strip().lower() in ('1', 'true', 'si', 'sí')


# --- Lo básico ---
# Con DEBUG=True, cualquier error le mostraría a un visitante tu código,
# tus rutas y tu configuración. En producción: siempre apagado.
DEBUG = False
SECRET_KEY = _obligatoria('DJANGO_SECRET_KEY')
# Dominios que este servidor acepta, separados por coma:
#   DJANGO_ALLOWED_HOSTS=www.tudominio.mx,tudominio.mx
ALLOWED_HOSTS = [h.strip() for h in _obligatoria('DJANGO_ALLOWED_HOSTS').split(',') if h.strip()]
# El RSVP se manda por fetch con token CSRF; Django revisa que venga de uno
# de estos orígenes (los mismos dominios, con https).
CSRF_TRUSTED_ORIGINS = [
    'https://*' + h if h.startswith('.') else f'https://{h}' for h in ALLOWED_HOSTS
]
ADMIN_URL = os.environ.get('DJANGO_ADMIN_URL', 'admin/').strip('/') + '/'


# --- HTTPS ---
# Las cookies de sesión (admin) y CSRF solo viajan cifradas
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# El hosting recibe el HTTPS y le pasa la petición a Django por dentro. Si
# tu hosting manda la cabecera X-Forwarded-Proto (y borra la que mande el
# visitante), actívalo con DJANGO_PROXY_HTTPS=1: así Django sabe que la
# petición original fue HTTPS y puede redirigir y mandar HSTS él mismo.
# En PythonAnywhere basta con el interruptor "Force HTTPS" de la pestaña Web.
if _si_no('DJANGO_PROXY_HTTPS', False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    # Empieza en 1 hora; cuando todo funcione bien por HTTPS, súbelo a
    # 31536000 (1 año) en el .env.
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SEGUNDOS', '3600'))
else:
    # La redirección a HTTPS la hace el hosting ("Force HTTPS"), así que
    # estos dos avisos de "check --deploy" no aplican. HSTS necesita que
    # Django sepa que la petición fue HTTPS: se activa con DJANGO_PROXY_HTTPS=1.
    SILENCED_SYSTEM_CHECKS = ['security.W004', 'security.W008']


# --- Archivos estáticos: WhiteNoise ---
# Con DEBUG=False Django ya no sirve /static/. WhiteNoise lo hace desde el
# propio Django (comprimido, con caché larga y soporte de audio por
# pedazos para el iPhone). "collectstatic" los junta en STATIC_ROOT.
MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1,
                  'whitenoise.middleware.WhiteNoiseMiddleware')
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
# OJO: las FOTOS subidas (media/) no las sirve WhiteNoise: se configuran en
# el hosting (en PythonAnywhere: "Static files" → /media/ → carpeta media).


# --- Caché compartida (para el límite anti-spam) ---
# La caché en memoria es por proceso; el servidor corre varios procesos y
# cada uno llevaría su propia cuenta. En archivo, todos comparten la misma.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': BASE_DIR / '.cache',
    }
}
# En PythonAnywhere la IP real del invitado llega en X-Real-IP (la de
# REMOTE_ADDR es la del balanceador y sería la misma para todos).
CABECERA_IP_CLIENTE = os.environ.get('DJANGO_CABECERA_IP', 'HTTP_X_REAL_IP')


# --- Correo ---
# Hoy el sistema no manda correos; queda listo el backend SMTP (Django 6.1
# no acepta el de "consola" en producción). Si algún día se usa, los datos
# van en el .env.
MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
        'OPTIONS': {
            'host': os.environ.get('CORREO_SMTP_HOST', 'localhost'),
            'port': int(os.environ.get('CORREO_SMTP_PUERTO', '587')),
            'username': os.environ.get('CORREO_SMTP_USUARIO', ''),
            'password': os.environ.get('CORREO_SMTP_CONTRASENA', ''),
            'use_tls': _si_no('CORREO_SMTP_TLS', True),
        },
    },
}


# --- Errores ---
# Sin DEBUG, los errores ya no se ven en pantalla: se escriben en la salida
# de errores, que el hosting guarda en su "error log".
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'consola': {'class': 'logging.StreamHandler'}},
    'loggers': {
        'django': {'handlers': ['consola'], 'level': 'ERROR'},
        'invitaciones': {'handlers': ['consola'], 'level': 'WARNING'},
    },
}
