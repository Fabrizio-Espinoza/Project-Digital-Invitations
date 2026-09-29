from django.contrib import admin
from django.db.models import Count
from .models import Plantilla, Invitacion, ImagenGaleria, Confirmacion


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
