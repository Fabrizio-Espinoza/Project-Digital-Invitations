import json
from django.contrib.staticfiles import finders
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, get_object_or_404
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import Invitacion, Confirmacion


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
