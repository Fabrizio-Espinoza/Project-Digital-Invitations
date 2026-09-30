from django.contrib import admin, messages
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

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


@admin.register(Invitacion)
class InvitacionAdmin(admin.ModelAdmin):
    # list_display es lo que ves de un vistazo en la tabla general:
    # aquí metí un método (total_confirmados) para no tener que entrar
    # a cada invitación a contar manualmente cuánta gente ya dijo que sí.
    list_display = ("titulo_evento", "plantilla", "nivel", "fecha_evento", "activa", "total_confirmados")
    list_filter = ("nivel", "plantilla__tipo_evento", "activa")
    search_fields = ("titulo_evento", "anfitriones", "slug")
    readonly_fields = ("id", "slug", "creada_en", "resumen_votacion")
    inlines = [ImagenGaleriaInline, ConfirmacionInline]

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



@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    """
    Flujo: 1) creas el pedido (cliente, diseño, paquete) y guardas;
    2) copias el mensaje con el link y se lo mandas por WhatsApp;
    3) el cliente llena sus datos y se crea su invitación como borrador;
    4) la revisas con "Vista previa" y la publicas con la acción de la lista.
    """
    list_display = ("cliente", "plantilla", "nivel", "estado", "creado_en")
    list_filter = ("es_demo", "plantilla__tipo_evento", "nivel")
    search_fields = ("cliente", "invitacion__anfitriones")
    readonly_fields = ("link_para_el_cliente", "invitacion_creada", "cancion", "notas", "enviado_en")
    fields = ("cliente", "plantilla", "nivel", "es_demo", "link_para_el_cliente", "invitacion_creada", "cancion", "notas", "enviado_en")
    actions = ["publicar"]

    @admin.display(description="Estado")
    def estado(self, obj):
        if obj.es_demo:
            return "🧪 Demo (no guarda nada)"
        if obj.invitacion is None:
            return "⏳ Esperando datos"
        return "✅ Publicada" if obj.invitacion.activa else "📝 Datos recibidos: revisar"

    @admin.display(description="Link para el cliente")
    def link_para_el_cliente(self, obj):
        if not obj.pk:
            return "Guarda el pedido y aquí aparece el link."
        ruta = reverse("pedido", args=[obj.token])
        # el dominio lo pone el navegador (location.origin): sirve igual en la compu, el túnel o el servidor
        mensaje = ("¡Hola! Aquí puedes llenar los datos de tu invitación. Toma unos 10 minutos "
                   "y al terminar ves cómo va quedando: ")
        return format_html(
            '<code>{}</code><br>'
            '<button type="button" class="button" onclick="navigator.clipboard.writeText(location.origin + \'{}\'); this.textContent = \'¡Copiado!\'">Copiar link</button> '
            '<button type="button" class="button" onclick="navigator.clipboard.writeText(\'{}\' + location.origin + \'{}\'); this.textContent = \'¡Copiado!\'">Copiar mensaje para WhatsApp</button> '
            '<a class="button" href="{}" target="_blank" rel="noopener">Abrir</a>',
            ruta, ruta, mensaje, ruta, ruta,
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
            self.message_user(request, f"Publicadas: {publicadas}. Ya puedes mandar el link a tu cliente.")
        else:
            self.message_user(request, "No había invitaciones por publicar (sin datos o ya publicadas).", messages.WARNING)
