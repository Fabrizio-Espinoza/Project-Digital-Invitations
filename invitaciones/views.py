import json
from datetime import timedelta, timezone as dt_timezone

from django.contrib.staticfiles import finders
from django.db.models import Count
from django.http import Http404, HttpResponse, JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, get_object_or_404
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import Invitacion, Confirmacion, Voto

# Duración que se le pone al evento en el calendario del invitado. La
# invitación solo guarda la hora de inicio; 4 h cubre bien un baby shower
# o una fiesta y el invitado lo puede ajustar en su calendario.
DURACION_EVENTO_HORAS = 4


def _votacion_habilitada(invitacion):
    """
    Regresa la configuración de la votación si esta invitación puede
    mostrarla, o None si no. Misma idea que mostrar_rsvp/mostrar_musica:
    cruza lo que el cliente pagó (premium = "extras"), lo que la plantilla
    sabe dibujar (soporta_votacion) y si de verdad se configuraron opciones
    en contenido_extra. Las 3 vistas de votación usan esta misma regla.
    """
    votacion = (invitacion.contenido_extra or {}).get("votacion") or {}
    if (
        invitacion.nivel == "premium"
        and invitacion.plantilla.soporta_votacion
        and votacion.get("opciones")
    ):
        return votacion
    return None


def _resumen_votacion(invitacion, votacion):
    """
    Conteo por opción + total + resultado revelado (si ya lo hay). Solo se
    cuentan las claves que existen hoy en la configuración, así que renombrar
    o quitar una opción desde el admin no rompe el porcentaje.
    """
    claves = [opcion.get("clave") for opcion in votacion["opciones"]]
    votos = dict(
        invitacion.votos.values_list("opcion").annotate(total=Count("id")).order_by()
    )
    conteos = {clave: votos.get(clave, 0) for clave in claves}
    resultado = votacion.get("resultado") or ""
    return {
        "conteos": conteos,
        "total": sum(conteos.values()),
        "resultado": resultado if resultado in claves else "",
    }



def iconos_pwa(plantilla):
    """
    Cada diseño puede traer su propio ícono de app en
    static/invitaciones/pwa/<slug_tema>-<tamaño>.png. Si todavía no existe
    (plantilla nueva), se usa el ícono genérico "default" para que la
    invitación siga siendo instalable.
    """
    base = f"invitaciones/pwa/{plantilla.slug_tema}"
    if not finders.find(f"{base}-192.png"):
        base = "invitaciones/pwa/default"
    return {tamano: static(f"{base}-{tamano}.png") for tamano in (180, 192, 512)}

@ensure_csrf_cookie
def detalle_invitacion(request, slug):
    """
    Vista pública: la que abre el invitado cuando entra a tuapp.com/<slug>.
    Trae la invitación + su plantilla + galería en una sola consulta
    (select_related y prefetch_related evitan que Django haga una query
    extra por cada relación cuando el template las use).
    """
    invitacion = get_object_or_404(
        Invitacion.objects.select_related("plantilla").prefetch_related("galeria"),
        slug=slug,
        activa=True,
    )

    contexto = {
        "invitacion": invitacion,
        "plantilla": invitacion.plantilla,
        # nivel controla qué bloques pinta el template (ver comentario en el HTML)
        "mostrar_rsvp": invitacion.nivel != "imagen" and invitacion.plantilla.soporta_rsvp,
        "mostrar_musica": invitacion.nivel == "premium" and invitacion.plantilla.soporta_musica,
        "mostrar_galeria": invitacion.nivel != "imagen" and invitacion.plantilla.soporta_galeria,
        "iconos_pwa": iconos_pwa(invitacion.plantilla),
    }
    votacion = _votacion_habilitada(invitacion)
    contexto["mostrar_votacion"] = votacion is not None
    contexto["votacion"] = votacion or {}
    # el nombre de la plantilla HTML sale del slug_tema, así cada diseño
    # es literalmente un archivo distinto y no si/else gigantes en un solo template
    return render(request, f"invitaciones/temas/{invitacion.plantilla.slug_tema}.html", contexto)


@require_POST
def enviar_confirmacion(request, slug):
    """
    Recibe el formulario de RSVP por fetch/AJAX (no recarga la página).
    Devuelve JSON para que el front actualice el contador sin refrescar.
    """
    invitacion = get_object_or_404(Invitacion, slug=slug, activa=True)
    data = json.loads(request.body)

    confirmacion = Confirmacion.objects.create(
        invitacion=invitacion,
        nombre_invitado=data.get("nombre_invitado", "").strip(),
        asistencia=data.get("asistencia"),
        num_acompanantes=int(data.get("num_acompanantes", 0)),
        mensaje=data.get("mensaje", "").strip(),
    )

    return JsonResponse({
        "ok": True,
        "total_confirmados": invitacion.confirmaciones.filter(asistencia="si").count(),
    })


def conteo_confirmados(request, slug):
    """
    Endpoint ligero que solo regresa el número actual de confirmados.
    El front lo consulta cada pocos segundos (polling) para simular
    'tiempo real' sin necesitar websockets/Django Channels todavía.
    Cuando el negocio crezca y quieras algo más instantáneo, este es
    el punto exacto donde se reemplaza por un socket.
    """
    invitacion = get_object_or_404(Invitacion, slug=slug, activa=True)
    return JsonResponse({
        "total_confirmados": invitacion.confirmaciones.filter(asistencia="si").count(),
    })


@require_POST
def enviar_voto(request, slug):
    """
    Registra una predicción del juego de votación y regresa el conteo
    actualizado para que el front pinte las barras al instante.
    Una vez que el anfitrión revela el resultado, la votación se cierra.
    """
    invitacion = get_object_or_404(
        Invitacion.objects.select_related("plantilla"), slug=slug, activa=True
    )
    votacion = _votacion_habilitada(invitacion)
    if votacion is None:
        raise Http404("Esta invitación no tiene votación.")

    resumen = _resumen_votacion(invitacion, votacion)
    if resumen["resultado"]:
        return JsonResponse({"ok": False, "error": "La votación ya cerró.", **resumen}, status=400)

    try:
        opcion = json.loads(request.body).get("opcion")
    except (json.JSONDecodeError, AttributeError):
        opcion = None
    if not isinstance(opcion, str) or opcion not in resumen["conteos"]:
        return JsonResponse({"ok": False, "error": "Opción no válida."}, status=400)

    Voto.objects.create(invitacion=invitacion, opcion=opcion)
    return JsonResponse({"ok": True, **_resumen_votacion(invitacion, votacion)})


def conteo_votos(request, slug):
    """
    Igual que conteo_confirmados: el front lo consulta cada pocos segundos.
    Además del conteo trae el resultado, así cuando el anfitrión lo revela
    desde el admin, a todos los invitados con la invitación abierta les
    aparece "¡Es niña!" / "¡Es niño!" sin recargar la página.
    """
    invitacion = get_object_or_404(
        Invitacion.objects.select_related("plantilla"), slug=slug, activa=True
    )
    votacion = _votacion_habilitada(invitacion)
    if votacion is None:
        raise Http404("Esta invitación no tiene votación.")
    return JsonResponse(_resumen_votacion(invitacion, votacion))


def _escapar_ics(texto):
    """El formato iCalendar trata \\ ; , y saltos de línea como caracteres especiales."""
    return (
        str(texto)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _plegar_linea_ics(linea):
    """
    El estándar pide líneas de máximo 75 bytes; las que siguen empiezan con
    un espacio. Se mide en bytes (no en letras) porque "ñ" o "á" ocupan 2.
    """
    partes, actual, tamano = [], "", 0
    for caracter in linea:
        bytes_caracter = len(caracter.encode("utf-8"))
        if tamano + bytes_caracter > 75:
            partes.append(actual)
            actual, tamano = " ", 1
        actual += caracter
        tamano += bytes_caracter
    partes.append(actual)
    return "\r\n".join(partes)


def calendario_ics(request, slug):
    """
    Botón "Agendar": genera al vuelo un archivo .ics (el estándar que
    entienden Calendario de iPhone, Google Calendar y Outlook) con la fecha,
    el lugar, el link de la invitación y un recordatorio un día antes.
    No se guarda nada: todo sale de los datos que ya tiene la invitación.
    """
    invitacion = get_object_or_404(Invitacion, slug=slug, activa=True)
    extra = invitacion.contenido_extra or {}

    def en_utc(fecha):
        return fecha.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    url_invitacion = request.build_absolute_uri(
        reverse("invitaciones:detalle", args=[invitacion.slug])
    )
    lugar = invitacion.lugar_nombre or extra.get("lugar_ceremonia_nombre", "")
    if extra.get("lugar_direccion"):
        lugar = f"{lugar}, {extra['lugar_direccion']}" if lugar else extra["lugar_direccion"]

    lineas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Invitaciones Digitales//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{invitacion.id}@invitaciones",
        f"DTSTAMP:{en_utc(timezone.now())}",
        f"DTSTART:{en_utc(invitacion.fecha_evento)}",
        f"DTEND:{en_utc(invitacion.fecha_evento + timedelta(hours=DURACION_EVENTO_HORAS))}",
        f"SUMMARY:{_escapar_ics(invitacion.titulo_evento)}",
    ]
    if lugar:
        lineas.append(f"LOCATION:{_escapar_ics(lugar)}")
    lineas += [
        f"DESCRIPTION:{_escapar_ics('Tu invitación: ' + url_invitacion)}",
        f"URL:{url_invitacion}",
        "BEGIN:VALARM",
        "TRIGGER:-P1D",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_escapar_ics('Mañana: ' + invitacion.titulo_evento)}",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    contenido = "\r\n".join(_plegar_linea_ics(linea) for linea in lineas) + "\r\n"

    respuesta = HttpResponse(contenido, content_type="text/calendar; charset=utf-8")
    respuesta["Content-Disposition"] = f'attachment; filename="{invitacion.slug}.ics"'
    return respuesta


def manifest_invitacion(request, slug):
    """
    El manifest es la "ficha" que lee el celular al instalar la invitación
    como app: nombre bajo el ícono, ícono, colores y en qué URL abre.
    Se genera por invitación (no es un archivo estático) para que cada
    evento se instale con su propio nombre y abra directo en SU página.
    """
    invitacion = get_object_or_404(Invitacion.objects.select_related("plantilla"), slug=slug, activa=True)
    url_invitacion = reverse("invitaciones:detalle", args=[invitacion.slug])
    iconos = iconos_pwa(invitacion.plantilla)
    color = invitacion.plantilla.color_tema

    manifest = {
        # id estable: si el invitado reinstala, el sistema sabe que es la misma app
        "id": url_invitacion,
        "name": invitacion.titulo_evento,
        "short_name": invitacion.anfitriones,
        "description": invitacion.mensaje_bienvenida,
        "lang": "es-MX",
        "start_url": url_invitacion,
        # scope limitado a esta invitación: si el invitado sale a otra URL
        # (mapa, mesa de regalos) se abre fuera de la "app"
        "scope": url_invitacion,
        "display": "standalone",
        "orientation": "portrait",
        "background_color": color,
        "theme_color": color,
        "icons": [
            {"src": iconos[192], "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": iconos[512], "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": iconos[512], "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    return JsonResponse(
        manifest,
        content_type="application/manifest+json",
        json_dumps_params={"ensure_ascii": False},
    )


def service_worker(request):
    """
    Sirve el service worker desde /invitaciones/sw.js y no desde /static/:
    un service worker solo puede controlar páginas que están "debajo" de
    la carpeta desde donde se sirve. Si viviera en /static/ no podría
    controlar /invitaciones/<slug>/.
    """
    respuesta = render(request, "invitaciones/pwa/sw.js", content_type="application/javascript")
    # el navegador debe revisar siempre si hay versión nueva del SW
    respuesta["Cache-Control"] = "no-cache"
    return respuesta
