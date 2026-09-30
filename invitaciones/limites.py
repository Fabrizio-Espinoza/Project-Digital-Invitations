"""
Límite de envíos (rate limit) para el RSVP y la votación.

Sin esto, cualquiera puede mandar cientos de confirmaciones falsas con un
fetch directo al endpoint (sin pasar por el formulario) y arruinar el
conteo que ve el cliente. La idea es sencilla: cada envío suma 1 en un
contador de la caché que se reinicia solo al terminar su ventana de tiempo;
si el contador pasa del máximo, se responde 429 ("demasiadas peticiones").

La IP nunca se guarda tal cual: la llave usa un hash de la IP con la
SECRET_KEY, y desaparece sola de la caché al vencer su ventana.
"""
import hashlib
import logging
import time

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def ip_cliente(request):
    """
    IP del invitado. Detrás del balanceador de un hosting, REMOTE_ADDR es
    la del balanceador (igual para todos) y la real llega en otra cabecera
    (CABECERA_IP_CLIENTE en settings). De X-Forwarded-For solo se confía en
    el último valor: los anteriores los puede inventar el propio visitante.
    """
    cabecera = getattr(settings, "CABECERA_IP_CLIENTE", "REMOTE_ADDR")
    valor = request.META.get(cabecera) or request.META.get("REMOTE_ADDR", "")
    if cabecera == "HTTP_X_FORWARDED_FOR":
        valor = valor.split(",")[-1]
    return valor.strip()


def _huella(texto):
    return hashlib.sha256(f"{settings.SECRET_KEY}:{texto}".encode()).hexdigest()[:24]


def _sumar(llave, ventana):
    """Suma 1 al contador de la ventana actual y regresa el total."""
    numero_ventana = int(time.time() // ventana)
    llave = f"limite:{llave}:{numero_ventana}"
    cache.add(llave, 0, ventana + 5)
    try:
        return cache.incr(llave)
    except ValueError:   # expiró justo entre add e incr
        cache.set(llave, 1, ventana + 5)
        return 1


def limite_superado(request, accion, invitacion, limites):
    """
    Cuenta este envío y dice si ya se pasó de alguno de los límites.
    `limites` = {"por_ip": (maximo, segundos), "por_invitacion": (maximo, segundos)}.
    """
    maximo_ip, ventana_ip = limites["por_ip"]
    maximo_inv, ventana_inv = limites["por_invitacion"]
    por_ip = _sumar(f"{accion}:{invitacion.pk}:{_huella(ip_cliente(request))}", ventana_ip)
    por_invitacion = _sumar(f"{accion}:{invitacion.pk}", ventana_inv)
    superado = por_ip > maximo_ip or por_invitacion > maximo_inv
    if superado:
        logger.warning("Límite de %s superado en la invitación %s (ip=%s, total=%s)",
                       accion, invitacion.slug, por_ip, por_invitacion)
    return superado
