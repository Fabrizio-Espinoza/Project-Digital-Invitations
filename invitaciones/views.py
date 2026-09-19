import json
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import Invitacion, Confirmacion

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
