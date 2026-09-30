import json
import re
from datetime import timedelta, timezone as dt_timezone
from urllib.parse import quote

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import Http404, HttpResponse, JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .catalogo import DISENOS, TIPOS, captura
from .limites import limite_superado
from .models import Invitacion, Confirmacion, Pedido, Voto
from .pedidos import MAX_FOTOS, FormularioPedido, datos_iniciales, guardar_pedido, leer_filas, preparar_foto

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
    return _pintar_invitacion(request, invitacion)


def _pintar_invitacion(request, invitacion, **extra):
    """La invitación con su plantilla. La usan la vista pública y la vista previa del pedido."""
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
    contexto.update(extra)
    # el nombre de la plantilla HTML sale del slug_tema, así cada diseño
    # es literalmente un archivo distinto y no si/else gigantes en un solo template
    return render(request, f"invitaciones/temas/{invitacion.plantilla.slug_tema}.html", contexto)


MAX_MENSAJE = 1000
# Si el mismo nombre manda la misma respuesta dentro de esta ventana (doble
# toque al botón, conexión lenta), no se cuenta dos veces.
VENTANA_DUPLICADO = timedelta(minutes=10)


def _error(mensaje, status=400, **extra):
    return JsonResponse({"ok": False, "error": mensaje, **extra}, status=status)


def _demasiados_envios():
    respuesta = _error(
        "Recibimos demasiados envíos desde tu conexión. Espera unos minutos e inténtalo de nuevo.",
        status=429,
    )
    respuesta["Retry-After"] = "600"
    return respuesta


def _validar_rsvp(data):
    """
    Revisa lo que mandó el navegador. Regresa (datos_limpios, None) o
    (None, "mensaje de error"). El formulario ya valida en el navegador,
    pero cualquiera puede mandar un fetch directo con lo que quiera: el
    servidor nunca debe confiar en lo que llega.
    """
    if not isinstance(data, dict):
        return None, "Datos no válidos."
    nombre = data.get("nombre_invitado")
    nombre = nombre.strip() if isinstance(nombre, str) else ""
    if not nombre:
        return None, "Escribe tu nombre."
    if len(nombre) > Confirmacion._meta.get_field("nombre_invitado").max_length:
        return None, "El nombre es demasiado largo."

    asistencia = data.get("asistencia")
    if asistencia not in dict(Confirmacion.ASISTENCIA):
        return None, "Elige si vas a asistir."

    try:
        acompanantes = int(str(data.get("num_acompanantes", 0)).strip() or 0)
    except ValueError:
        return None, "El número de acompañantes no es válido."
    if not 0 <= acompanantes <= settings.MAX_ACOMPANANTES:
        return None, f"El número de acompañantes debe estar entre 0 y {settings.MAX_ACOMPANANTES}."

    mensaje = data.get("mensaje") or ""
    mensaje = mensaje.strip() if isinstance(mensaje, str) else ""
    if len(mensaje) > MAX_MENSAJE:
        return None, f"El mensaje es demasiado largo (máximo {MAX_MENSAJE} caracteres)."

    return {
        "nombre_invitado": nombre,
        "asistencia": asistencia,
        "num_acompanantes": acompanantes,
        "mensaje": mensaje,
    }, None


@require_POST
def enviar_confirmacion(request, slug):
    """
    Recibe el formulario de RSVP por fetch/AJAX (no recarga la página).
    Devuelve JSON para que el front actualice el contador sin refrescar.
    Antes de guardar: límite anti-spam, validación y descarte de duplicados.
    """
    invitacion = get_object_or_404(Invitacion, slug=slug, activa=True)
    if limite_superado(request, "rsvp", invitacion, settings.LIMITES_RSVP):
        return _demasiados_envios()

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        data = None
    datos, error = _validar_rsvp(data)
    if error:
        return _error(error)

    ya_estaba = invitacion.confirmaciones.filter(
        nombre_invitado__iexact=datos["nombre_invitado"],
        asistencia=datos["asistencia"],
        creada_en__gte=timezone.now() - VENTANA_DUPLICADO,
    ).exists()
    if not ya_estaba:
        Confirmacion.objects.create(invitacion=invitacion, **datos)

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
    if limite_superado(request, "voto", invitacion, settings.LIMITES_VOTO):
        return _demasiados_envios()

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


def aviso_privacidad(request):
    """
    Aviso de privacidad integral (Ley Federal de Protección de Datos
    Personales en Posesión de los Particulares). Los datos del responsable
    salen de settings (.env en producción) para no tenerlos en el código.
    """
    return render(request, "invitaciones/privacidad.html", {
        "marca": settings.MARCA_NOMBRE,
        "responsable": settings.AVISO_RESPONSABLE,
        "domicilio": settings.AVISO_DOMICILIO,
        "correo": settings.AVISO_CORREO,
        "actualizado": settings.AVISO_ACTUALIZADO,
        "dias_retencion": settings.DIAS_RETENCION_DATOS,
    })


def enlace_whatsapp(texto):
    """
    Link que abre WhatsApp con el mensaje ya escrito. WHATSAPP_NUMERO va con
    lada de país (52 + 10 dígitos); se le quitan espacios y guiones por si
    se capturó "+52 55 1234 5678". Sin número, WhatsApp deja elegir el chat.
    """
    numero = re.sub(r"\D", "", settings.WHATSAPP_NUMERO)
    return f"https://wa.me/{numero}?text={quote(texto)}"


def catalogo(request):
    """
    Página principal (/): el escaparate que se manda por WhatsApp y al que
    llegan los anuncios. Cada diseño enseña su captura, abre su demo real y
    tiene su botón "La quiero" con el mensaje ya escrito, así el vendedor
    sabe de inmediato qué diseño y qué evento le interesan al cliente.
    """
    demos_publicados = set(
        Invitacion.objects.filter(slug__in=[d["demo"] for d in DISENOS], activa=True)
        .values_list("slug", flat=True)
    )
    grupos = []
    for clave, titulo, para in TIPOS:
        disenos = [
            {
                **diseno,
                "captura": captura(diseno),
                # si el demo aún no se creó en esta base, la tarjeta se muestra sin link (no a un 404)
                "demo_url": reverse("invitaciones:detalle", args=[diseno["demo"]])
                if diseno["demo"] in demos_publicados else "",
                "whatsapp": enlace_whatsapp(
                    f"¡Hola! Me interesa la invitación «{diseno['nombre']}» para {para}. ¿Me das información?"
                ),
            }
            for diseno in DISENOS if diseno["tipo"] == clave
        ]
        grupos.append({"clave": clave, "titulo": titulo, "disenos": disenos})

    por_nombre = {d["nombre"]: d for grupo in grupos for d in grupo["disenos"]}
    return render(request, "invitaciones/catalogo.html", {
        "marca": settings.MARCA_NOMBRE,
        "grupos": grupos,
        "total": len(DISENOS),
        # los tres celulares de la portada: XV, boda y baby shower (tres públicos distintos)
        "portada": [por_nombre[n] for n in ("La Gira", "Hotel Amor", "Pancito en el Horno")],
        "whatsapp_general": enlace_whatsapp("¡Hola! Quiero cotizar una invitación digital."),
        "imagen_compartir": _url_absoluta(request, static("invitaciones/catalogo/compartir.jpg")),
    })


def _url_absoluta(request, ruta):
    """
    Open Graph pide URL absoluta (es la foto que sale al pegar el link en
    WhatsApp). En producción el hosting recibe el HTTPS y le pasa a Django
    la petición como http, así que ahí se fuerza https: el sitio solo se
    sirve por HTTPS ("Force HTTPS").
    """
    url = request.build_absolute_uri(ruta)
    if not settings.DEBUG and url.startswith("http://"):
        url = "https://" + url.removeprefix("http://")
    return url


def _diseno_del_catalogo(plantilla):
    """Nombre comercial y captura del diseño (si está en el catálogo)."""
    for diseno in DISENOS:
        if diseno["slug_tema"] == plantilla.slug_tema:
            return {**diseno, "captura": captura(diseno)}
    return {"nombre": plantilla.nombre, "captura": ""}


def pedido(request, token):
    """
    Formulario privado del cliente (/pedido/<token>/). Al enviarlo se crea
    o se actualiza su invitación como borrador; se puede volver a abrir
    para corregir hasta que la invitación se publica.
    """
    pedido = get_object_or_404(Pedido.objects.select_related("plantilla", "invitacion"), token=token)
    contexto = {
        "marca": settings.MARCA_NOMBRE,
        "pedido": pedido,
        "diseno": _diseno_del_catalogo(pedido.plantilla),
        "whatsapp": enlace_whatsapp(
            f"¡Hola! Tengo una duda con los datos de mi invitación «{_diseno_del_catalogo(pedido.plantilla)['nombre']}»."
        ),
    }
    if not pedido.abierto:
        return _respuesta_privada(render(request, "invitaciones/pedido.html", {**contexto, "cerrado": True}))
    if request.GET.get("listo") and pedido.invitacion:
        return _respuesta_privada(render(request, "invitaciones/pedido.html", {**contexto, "listo": True}))

    galeria = list(pedido.invitacion.galeria.all()) if pedido.invitacion else []
    errores = []
    if request.method == "POST":
        formulario = FormularioPedido(request.POST, pedido=pedido)
        filas, errores = leer_filas(request.POST, formulario.repetibles())
        fotos, borrar = [], []
        if formulario.con_galeria:
            ids = {str(foto.pk) for foto in galeria}
            borrar = [pk for pk in request.POST.getlist("borrar_foto") if pk in ids]
            archivos = request.FILES.getlist("fotos")
            if len(galeria) - len(borrar) + len(archivos) > MAX_FOTOS:
                errores.append(f"Máximo {MAX_FOTOS} fotos en total.")
            else:
                for archivo in archivos:
                    try:
                        fotos.append(preparar_foto(archivo))
                    except ValidationError as error:
                        errores.extend(error.messages)
        if formulario.is_valid() and not errores:
            guardar_pedido(pedido, formulario.cleaned_data, filas, fotos, borrar)
            return redirect(f"{reverse('pedido', args=[token])}?listo=1")
        if request.FILES:
            errores.append("Por seguridad, vuelve a elegir tus fotos antes de enviar.")
    else:
        iniciales, filas = datos_iniciales(pedido)
        formulario = FormularioPedido(initial=iniciales, pedido=pedido)

    return _respuesta_privada(render(request, "invitaciones/pedido.html", {
        **contexto,
        "formulario": formulario,
        "secciones": formulario.secciones(filas),
        "errores": errores,
        "galeria": galeria,
        "max_fotos": MAX_FOTOS,
    }))


def pedido_vista_previa(request, token):
    """
    La invitación del pedido tal como va a quedar, aunque todavía no esté
    publicada. Lleva marca de agua "VISTA PREVIA" y su RSVP no funciona
    (la invitación está inactiva): sirve para revisar, no para mandarla a
    los invitados. La versión limpia es la que tú publicas.
    """
    pedido = get_object_or_404(Pedido.objects.select_related("invitacion"), token=token)
    if pedido.invitacion is None:
        return redirect("pedido", token=token)
    if pedido.invitacion.activa:
        # ya publicada: la vista previa (con marca de agua) deja de existir
        return redirect("invitaciones:detalle", slug=pedido.invitacion.slug)
    invitacion = (Invitacion.objects.select_related("plantilla").prefetch_related("galeria")
                  .get(pk=pedido.invitacion.pk))
    return _respuesta_privada(_pintar_invitacion(request, invitacion, vista_previa=pedido))


def _respuesta_privada(respuesta):
    # links con token: que ningún buscador los guarde
    respuesta["X-Robots-Tag"] = "noindex, nofollow"
    respuesta["Cache-Control"] = "private, no-store"
    return respuesta
