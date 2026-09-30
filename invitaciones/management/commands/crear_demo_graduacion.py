from datetime import date, datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from invitaciones.models import Invitacion, Plantilla


class Command(BaseCommand):
    """
    Crea (o actualiza) la plantilla "Laurel de Oro" y una invitación de
    graduación de ejemplo, para ver el diseño sin capturar nada en el admin.

        python manage.py crear_demo_graduacion

    Es idempotente: correrlo dos veces no duplica registros, solo los
    actualiza (update_or_create busca por slug y sobreescribe los datos).
    """

    help = "Crea la plantilla de graduación y una invitación demo en /invitaciones/demo-graduacion/"

    def handle(self, *args, **options):
        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="graduacion-editorial-01",
            defaults={
                "nombre": "Laurel de Oro",
                "color_tema": "#0B1424",
                "tipo_evento": "graduacion",
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
            },
        )

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-graduacion",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Graduación de Valeria Montes",
                "anfitriones": "Valeria Montes",
                "fecha_evento": timezone.make_aware(datetime(2026, 12, 12, 18, 0)),
                "mensaje_bienvenida": (
                    "Después de años de esfuerzo, desvelos y sueños, llegó el momento "
                    "de celebrarlo. Me encantaría que fueras parte de este día."
                ),
                "fecha_limite_rsvp": date(2026, 11, 28),
                "contenido_extra": {
                    "carrera": "Licenciatura en Arquitectura",
                    "institucion": "Universidad Iberoamericana",
                    "generacion": "2022 — 2026",
                    "lugar_ceremonia_etiqueta": "Ceremonia",
                    "lugar_ceremonia_nombre": "Auditorio Sor Juana",
                    "lugar_ceremonia_mapa_url": "https://maps.google.com/?q=Universidad+Iberoamericana+CDMX",
                    "lugar_recepcion_etiqueta": "Celebración",
                    "lugar_recepcion_nombre": "Terraza Polanco",
                    "lugar_recepcion_mapa_url": "https://maps.google.com/?q=Polanco+CDMX",
                    "dresscode": "Formal · Etiqueta",
                    "dresscode_color": "#0B1424",
                    "itinerario": [
                        {"hora": "6:00 PM", "evento": "Ceremonia de graduación"},
                        {"hora": "7:30 PM", "evento": "Brindis y fotos"},
                        {"hora": "8:30 PM", "evento": "Cena"},
                        {"hora": "10:00 PM", "evento": "¡A bailar!"},
                    ],
                    "mesa_regalos_etiqueta": "Lluvia de sobres",
                    "mesa_regalos_url": "https://www.liverpool.com.mx/tienda/mesa-de-regalos",
                },
            },
        )

        accion = "Creada" if creada else "Actualizada"
        self.stdout.write(self.style.SUCCESS(
            f"{accion}: /invitaciones/{invitacion.slug}/ (plantilla {plantilla.slug_tema})"
        ))
