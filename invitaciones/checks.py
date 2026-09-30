"""
Revisiones propias para "python manage.py check --deploy": avisan de lo que
falta antes de publicar, igual que las de seguridad que ya trae Django.
"""
from django.conf import settings
from django.core.checks import Warning, register


@register(deploy=True)
def revisar_aviso_privacidad(app_configs, **kwargs):
    faltan = [
        nombre for nombre in ("AVISO_RESPONSABLE", "AVISO_DOMICILIO", "AVISO_CORREO")
        if not getattr(settings, nombre, "")
    ]
    if not faltan:
        return []
    return [Warning(
        "El aviso de privacidad tiene datos sin llenar: " + ", ".join(faltan) + ".",
        hint="Agrégalos al archivo .env del servidor (ver .env.ejemplo).",
        id="invitaciones.W001",
    )]


@register(deploy=True)
def revisar_ruta_admin(app_configs, **kwargs):
    if settings.ADMIN_URL.strip("/") == "admin":
        return [Warning(
            'El admin sigue en "/admin/", la primera ruta que prueban los bots.',
            hint="Cámbiala con DJANGO_ADMIN_URL en el .env.",
            id="invitaciones.W002",
        )]
    return []
