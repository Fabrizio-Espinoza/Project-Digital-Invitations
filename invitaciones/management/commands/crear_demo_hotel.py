"""
Crea (o actualiza) la plantilla de boda "Hotel Amor" y su invitación demo.

Uso:
    python manage.py crear_demo_hotel
    python manage.py crear_demo_hotel --host 192.168.1.50:8000

--host solo arma la URL absoluta de la música (musica_url es un URLField y
exige esquema + dominio). Para abrir el demo desde el iPhone por WiFi, pasa
la IP de tu compu. Acepta la IP con o sin "http://".

Es idempotente: correrlo varias veces actualiza el mismo registro.
"""
from datetime import date, datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from invitaciones.models import Invitacion, Plantilla


class Command(BaseCommand):
    help = "Crea o actualiza la invitación demo de boda 'Hotel Amor' (plantilla boda-hotel-03)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto desde el que se abrirá el demo (para la URL de la música).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].removeprefix("http://").removeprefix("https://").rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="boda-hotel-03",
            defaults={
                "nombre": "Hotel Amor",
                "tipo_evento": "boda",
                "color_tema": "#F5EDE0",   # barra del navegador en el celular (crema del toldo)
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
            },
        )

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-hotel-amor",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Boda de Sofía & Emiliano",
                "anfitriones": "Sofía & Emiliano",
                # hora local (TIME_ZONE = America/Mexico_City): sábado a las 6:00 PM
                "fecha_evento": timezone.make_aware(datetime(2027, 5, 8, 18, 0)),
                "mensaje_bienvenida": (
                    "Reservamos una habitación en nuestra historia a tu nombre. "
                    "Ven a celebrar que decidimos quedarnos juntos para siempre."
                ),
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": date(2027, 4, 1),
                "contenido_extra": {
                    "lugar_ceremonia_nombre": "Capilla de la hacienda",
                    "lugar_ceremonia_mapa_url": "https://maps.google.com/?q=Merida+Yucatan",
                    "lugar_recepcion_nombre": "Patio de los flamboyanes",
                    "lugar_recepcion_mapa_url": "https://maps.google.com/?q=Merida+Yucatan",
                    "dresscode": "Formal de verano · guayabera bienvenida",
                    "padrinos": [
                        {"rol": "Padres de la novia", "nombres": "Laura Méndez & Jorge Cervera"},
                        {"rol": "Padres del novio", "nombres": "Ana Solís & Raúl Aguilar"},
                    ],
                    "itinerario": [
                        {"hora": "6:00 PM", "evento": "Ceremonia en la capilla"},
                        {"hora": "7:00 PM", "evento": "Cóctel en el jardín"},
                        {"hora": "8:30 PM", "evento": "Cena"},
                        {"hora": "10:00 PM", "evento": "¡Fiesta!"},
                        {"hora": "1:00 AM", "evento": "Tornaboda con marquesitas"},
                    ],
                    "mesa_regalos_url": "https://mesaderegalos.liverpool.com.mx/",
                    "admite_ninos": False,
                },
                "activa": True,
            },
        )

        accion = "Creada" if creada else "Actualizada"
        self.stdout.write(self.style.SUCCESS(
            f"{accion}: http://{host}/invitaciones/{invitacion.slug}/ (plantilla {plantilla.slug_tema})"
        ))
