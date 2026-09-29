"""
Crea (o actualiza) la plantilla "Cobalto Editorial" y su invitación demo.

Uso:
    python manage.py crear_demo_cobalto
    python manage.py crear_demo_cobalto --host http://192.168.1.50:8000

--host solo se usa para armar la URL absoluta de la música (musica_url es un
URLField y exige esquema + dominio). Si vas a abrir el demo desde el iPhone
por WiFi, pasa la IP de tu compu en vez de 127.0.0.1.

Es idempotente: correrlo dos veces actualiza el mismo registro en vez de
duplicarlo (update_or_create busca por slug_tema / slug).
"""
from datetime import date, datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from invitaciones.models import Invitacion, Plantilla


class Command(BaseCommand):
    help = "Crea o actualiza la invitación demo de la plantilla Cobalto Editorial."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="http://127.0.0.1:8000",
            help="Origen desde el que se abrirá el demo (para la URL de la música).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="boda-editorial-02",
            defaults={
                "nombre": "Cobalto Editorial",
                "tipo_evento": "boda",
                "color_tema": "#1F3FA3",   # barra del navegador en el celular
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
            },
        )

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-cobalto-editorial",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Boda de Valentina & Mateo",
                "anfitriones": "Valentina & Mateo",
                "fecha_evento": timezone.make_aware(datetime(2027, 4, 17, 17, 30)),
                "lugar_nombre": "Ciudad de México",
                "mensaje_bienvenida": (
                    "Siete años, dos ciudades y un perro llamado Bruno después, "
                    "decidimos hacerlo oficial. Nos encantaría que fueras parte "
                    "de esta historia."
                ),
                "musica_url": f"{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": date(2027, 3, 20),
                "contenido_extra": {
                    "lugar_ceremonia_nombre": "Parroquia de San Jacinto, San Ángel",
                    "lugar_ceremonia_mapa_url": "https://maps.google.com/?q=Parroquia+de+San+Jacinto+San+Angel+CDMX",
                    "lugar_recepcion_nombre": "Hacienda Los Laureles, Tlalpan",
                    "lugar_recepcion_mapa_url": "https://maps.google.com/?q=Tlalpan+CDMX",
                    "dresscode": "Formal, en tonos azules",
                    "dresscode_color": "#1F3FA3",
                    "itinerario": [
                        {"hora": "5:30 PM", "evento": "Ceremonia religiosa"},
                        {"hora": "7:00 PM", "evento": "Cóctel de bienvenida"},
                        {"hora": "8:30 PM", "evento": "Cena y brindis"},
                        {"hora": "10:00 PM", "evento": "Primer baile y fiesta"},
                        {"hora": "2:00 AM", "evento": "Tornaboda"},
                    ],
                    "mesa_regalos_url": "https://mesaderegalos.liverpool.com.mx/",
                    "admite_ninos": False,
                },
                "activa": True,
            },
        )

        accion = "Creada" if creada else "Actualizada"
        self.stdout.write(self.style.SUCCESS(f"{accion}: {host}/invitaciones/{invitacion.slug}/"))
