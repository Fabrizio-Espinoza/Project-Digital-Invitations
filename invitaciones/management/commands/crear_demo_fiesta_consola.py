"""
Crea (o actualiza) la plantilla de fiesta "Nivel Desbloqueado" y su invitación demo.

Uso:
    python manage.py crear_demo_fiesta_consola
    python manage.py crear_demo_fiesta_consola --host 192.168.1.50:8000

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
    help = "Crea o actualiza la invitación demo de fiesta 'Nivel Desbloqueado' (plantilla fiesta-consola-03)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto desde el que se abrirá el demo (para la URL de la música).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].removeprefix("http://").removeprefix("https://").rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="fiesta-consola-03",
            defaults={
                "nombre": "Nivel Desbloqueado",
                "tipo_evento": "fiesta",
                "color_tema": "#E8E2D3",   # barra del navegador en el celular (plastico de la consola)
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
            },
        )

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-fiesta-rodrigo",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Los 30 de Rodrigo",
                "anfitriones": "Rodrigo",
                # hora local (TIME_ZONE = America/Mexico_City): sábado 8:00 PM
                "fecha_evento": timezone.make_aware(datetime(2026, 11, 14, 20, 0)),
                "lugar_nombre": "Bar La Palanca, Roma Norte",
                "lugar_mapa_url": "https://maps.google.com/?q=Roma+Norte+CDMX",
                "mensaje_bienvenida": (
                    "Treinta años, cero continues gastados. Esta partida no la juego "
                    "solo: te necesito en mi equipo para pasar de nivel."
                ),
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": date(2026, 11, 7),
                "contenido_extra": {
                    "nivel": "30",
                    "lugar_direccion": "Colima 145, Roma Norte",
                    "dresscode": "Casual · ponte algo retro",
                    "itinerario": [
                        {"hora": "8:00 PM", "evento": "Llegada y botanas"},
                        {"hora": "9:00 PM", "evento": "Torneo de videojuegos"},
                        {"hora": "10:30 PM", "evento": "Pastel y mañanitas"},
                        {"hora": "11:00 PM", "evento": "¡Fiesta!"},
                        {"hora": "1:00 AM", "evento": "Tacos: el jefe final"},
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
