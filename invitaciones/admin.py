from django import forms
from django.contrib import admin, messages
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from .fotos import LADO_MAXIMO_PORTADA, preparar_foto
from .models import Confirmacion, ImagenGaleria, Invitacion, Pedido, Plantilla


class ImagenGaleriaInline(admin.TabularInline):
    """
    Inline = puedes subir/reordenar las fotos de la galería directamente
    dentro de la pantalla de la Invitacion, sin entrar a otra sección del admin.
    """
    model = ImagenGaleria
    extra = 1


class ConfirmacionInline(admin.TabularInline):
    """
    Solo lectura: aquí NO quieres editar confirmaciones a mano, solo
    verlas de un vistazo mientras revisas una invitación específica.
    """
    model = Confirmacion
    extra = 0
    readonly_fields = ("nombre_invitado", "asistencia", "num_acompanantes", "mensaje", "creada_en")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Plantilla)
class PlantillaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo_evento", "slug_tema", "soporta_rsvp", "soporta_musica", "soporta_votacion")
    list_filter = ("tipo_evento",)


class FormularioInvitacion(forms.ModelForm):
    class Meta:
        model = Invitacion
        fields = "__all__"

    def clean_foto_portada(self):
        # la foto que subes aquí pasa por lo mismo que las del cliente:
        # derecha, achicada y sin EXIF (las fotos de celular traen el GPS)
        foto = self.cleaned_data.get("foto_portada")
        if isinstance(foto, UploadedFile):
            return preparar_foto(foto, LADO_MAXIMO_PORTADA)
        return foto


@admin.register(Invitacion)
class InvitacionAdmin(admin.ModelAdmin):
    # list_display es lo que ves de un vistazo en la tabla general:
    # aquí metí un método (total_confirmados) para no tener que entrar
    # a cada invitación a contar manualmente cuánta gente ya dijo que sí.
    list_display = ("titulo_evento", "plantilla", "nivel", "fecha_evento", "activa", "total_confirmados")
    list_filter = ("nivel", "plantilla__tipo_evento", "activa")
    search_fields = ("titulo_evento", "anfitriones", "slug")
    form = FormularioInvitacion
    readonly_fields = ("id", "slug", "creada_en", "panel_del_anfitrion", "resumen_votacion",
                       "cancion_pedida", "escuchar_cancion", "ver_portada")
    inlines = [ImagenGaleriaInline, ConfirmacionInline]
    # Secciones en el orden en que se atiende un pedido; lo técnico va al final y plegado
    fieldsets = (
        (None, {"fields": ("plantilla", "nivel", "activa", "slug", "panel_del_anfitrion")}),
        ("Evento", {"fields": ("titulo_evento", "anfitriones", "fecha_evento", "lugar_nombre",
                               "lugar_mapa_url", "mensaje_bienvenida", "fecha_limite_rsvp")}),
        ("Foto de portada", {"fields": ("foto_portada", "ver_portada")}),
        ("Música", {"fields": ("cancion_pedida", "musica_archivo", "escuchar_cancion", "musica_url")}),
        ("Votación", {"fields": ("resumen_votacion",)}),
        ("Detalles del tipo de evento (avanzado)", {"classes": ("collapse",), "fields": ("contenido_extra",)}),
        ("Registro", {"classes": ("collapse",), "fields": ("id", "creada_en")}),
    )

    @admin.display(description="Así se ve")
    def ver_portada(self, obj):
        src = obj.foto_portada_src if obj and not obj._state.adding else ""
        if not src:
            return "Sin foto todavía."
        nota = "" if obj.foto_portada else " (es la primera de la galería)"
        return format_html('<img src="{}" alt="" style="max-height: 220px; border-radius: 8px">{}', src, nota)

    @admin.display(description="Canción que pidió el cliente")
    def cancion_pedida(self, obj):
        pedido = getattr(obj, "pedido", None) if obj and not obj._state.adding else None
        return (pedido.cancion if pedido else "") or "—"

    @admin.display(description="Escuchar")
    def escuchar_cancion(self, obj):
        if obj is None or obj._state.adding or not obj.musica_src:
            return "Sin canción todavía."
        return format_html('<audio controls preload="none" src="{}" style="width: 100%; max-width: 360px"></audio>',
                           obj.musica_src)

    @admin.display(description="Panel del anfitrión")
    def panel_del_anfitrion(self, obj):
        if obj is None or obj._state.adding:
            return "Guarda la invitación y aquí aparece el link."
        return _botones_link(
            reverse("panel_anfitrion", args=[obj.token_panel]),
            "¡Tu invitación ya está lista! En este link privado ves quién confirma, cuántas personas van "
            "y los mensajes que te dejan (no lo compartas): ",
        )

    @admin.display(description="Confirmados")
    def total_confirmados(self, obj):
        return obj.confirmaciones.filter(asistencia="si").count()

    @admin.display(description="Votación en vivo")
    def resumen_votacion(self, obj):
        # Vista rápida de cómo va el juego de predicción (ej. "nina: 12 · nino: 8")
        # sin tener que abrir la invitación pública.
        if obj is None or obj._state.adding:
            return "—"
        conteos = obj.votos.values_list("opcion").annotate(total=Count("id")).order_by("opcion")
        if not conteos:
            return "Sin votos todavía"
        return " · ".join(f"{opcion}: {total}" for opcion, total in conteos)



def _botones_link(ruta, mensaje):
    """Ruta + botones Copiar link / Copiar mensaje para WhatsApp / Abrir. El dominio lo pone el navegador."""
    return format_html(
        '<code>{}</code><br>'
        '<button type="button" class="button" onclick="navigator.clipboard.writeText(location.origin + \'{}\'); this.textContent = \'¡Copiado!\'">Copiar link</button> '
        '<button type="button" class="button" onclick="navigator.clipboard.writeText(\'{}\' + location.origin + \'{}\'); this.textContent = \'¡Copiado!\'">Copiar mensaje para WhatsApp</button> '
        '<a class="button" href="{}" target="_blank" rel="noopener">Abrir</a>',
        ruta, ruta, mensaje, ruta, ruta,
    )


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    """
    Flujo: 1) creas el pedido (cliente, diseño, paquete) y guardas;
    2) copias el mensaje con el link y se lo mandas por WhatsApp;
    3) el cliente llena sus datos y se crea su invitación como borrador;
    4) la revisas con "Vista previa" y la publicas con la acción de la lista.
    """
    list_display = ("cliente", "plantilla", "nivel", "estado", "creado_en")
    list_filter = ("plantilla__tipo_evento", "nivel")
    search_fields = ("cliente", "invitacion__anfitriones")
    readonly_fields = ("link_para_el_cliente", "invitacion_creada", "cancion", "notas", "enviado_en")
    fields = ("cliente", "plantilla", "nivel", "link_para_el_cliente", "invitacion_creada", "cancion", "notas", "enviado_en")
    actions = ["publicar"]

    @admin.display(description="Estado")
    def estado(self, obj):
        if obj.invitacion is None:
            return "⏳ Esperando datos"
        return "✅ Publicada" if obj.invitacion.activa else "📝 Datos recibidos: revisar"

    @admin.display(description="Link para el cliente")
    def link_para_el_cliente(self, obj):
        if not obj.pk:
            return "Guarda el pedido y aquí aparece el link."
        return _botones_link(
            reverse("pedido", args=[obj.token]),
            "¡Hola! Aquí puedes llenar los datos de tu invitación. Toma unos 10 minutos "
            "y al terminar ves cómo va quedando: ",
        )

    @admin.display(description="Invitación")
    def invitacion_creada(self, obj):
        if obj.invitacion is None:
            return "Todavía no: el cliente no ha enviado sus datos."
        enlaces = format_html(
            '<a href="{}">Editar invitación</a> · <a href="{}" target="_blank" rel="noopener">Vista previa</a>',
            reverse("admin:invitaciones_invitacion_change", args=[obj.invitacion.pk]),
            reverse("pedido_vista_previa", args=[obj.token]),
        )
        if obj.invitacion.activa:
            publica = reverse("invitaciones:detalle", args=[obj.invitacion.slug])
            enlaces += format_html(' · Link para sus invitados: <a href="{}" target="_blank" rel="noopener">{}</a>', publica, publica)
        panel = reverse("panel_anfitrion", args=[obj.invitacion.token_panel])
        enlaces += format_html(' · <a href="{}" target="_blank" rel="noopener">Panel del anfitrión</a> (el link para copiárselo está en la invitación)', panel)
        return enlaces

    @admin.action(description="Publicar la invitación (el cliente ya no podrá editar sus datos)")
    def publicar(self, request, queryset):
        publicadas = 0
        for pedido in queryset.select_related("invitacion"):
            if pedido.invitacion and not pedido.invitacion.activa:
                pedido.invitacion.activa = True
                pedido.invitacion.save(update_fields=["activa"])
                publicadas += 1
        if publicadas:
            self.message_user(request, f"Publicadas: {publicadas}. Mándale a tu cliente el link de su invitación "
                                       "y el de su panel (en la invitación → «Panel del anfitrión»).")
        else:
            self.message_user(request, "No había invitaciones por publicar (sin datos o ya publicadas).", messages.WARNING)
