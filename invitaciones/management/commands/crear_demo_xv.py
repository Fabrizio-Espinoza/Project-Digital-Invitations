from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from invitaciones.models import Invitacion, Plantilla


class Command(BaseCommand):
    """
    Crea (o reutiliza) la Plantilla "Medianoche Dorada" y una invitación
    de XV años de ejemplo con TODAS las claves de contenido_extra llenas.
    Sirve para ver la plantilla completa sin capturar datos a mano en el
    admin, y como referencia viva de qué claves JSON existen.

    Uso:  python manage.py crear_demo_xv
    """
    help = "Crea una invitación de XV años de demostración (plantilla xv-medianoche-01)."

    def handle(self, *args, **options):
        plantilla, _ = Plantilla.objects.get_or_create(
            slug_tema="xv-medianoche-01",
            defaults={"nombre": "Medianoche Dorada", "tipo_evento": "xv", "color_tema": "#120E24"},
        )

        # localtime (no now): now() viene en UTC, y "19:00 UTC" se mostraba
        # como 1:00 PM en México. Con localtime las 7:00 PM son hora local.
        fecha = (timezone.localtime() + timedelta(days=60)).replace(hour=19, minute=0, second=0, microsecond=0)

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-xv-valentina",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "XV Años de Valentina",
                "anfitriones": "Valentina",
                "fecha_evento": fecha,
                "mensaje_bienvenida": "Hay momentos que se viven una sola vez. Quiero que estés conmigo en esta noche tan especial.",
                "fecha_limite_rsvp": (fecha - timedelta(days=15)).date(),
                "contenido_extra": {
                    "lugar_ceremonia_etiqueta": "Misa",
                    "lugar_ceremonia_nombre": "Parroquia de San Juan Bautista",
                    "lugar_ceremonia_mapa_url": "https://maps.google.com/?q=Parroquia+San+Juan+Bautista",
                    "lugar_recepcion_nombre": "Salón Cristal",
                    "lugar_recepcion_mapa_url": "https://maps.google.com/?q=Salon+Cristal",
                    "dresscode": "Formal — reservamos el rosa para la quinceañera",
                    "dresscode_color": "#F0A6C8",
                    "padres": "Laura Méndez & Ricardo Torres",
                    "padrinos": [
                        {"rol": "Padrinos de velación", "nombres": "Ana Ruiz & Jorge Salas"},
                        {"rol": "Padrinos de anillo", "nombres": "Sofía & Martín Torres"},
                    ],
                    "itinerario": [
                        {"hora": "6:00 PM", "evento": "Misa de acción de gracias"},
                        {"hora": "8:00 PM", "evento": "Recepción"},
                        {"hora": "9:00 PM", "evento": "Vals"},
                        {"hora": "10:00 PM", "evento": "Cena y fiesta"},
                    ],
                    "mesa_regalos_url": "https://www.liverpool.com.mx/",
                    "admite_ninos": True,
                },
            },
        )

        accion = "Creada" if creada else "Actualizada"
        self.stdout.write(self.style.SUCCESS(
            f"{accion}: /invitaciones/{invitacion.slug}/"
        ))
