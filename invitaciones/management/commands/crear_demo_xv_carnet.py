"""
Crea (o actualiza) la plantilla de XV "Carnet de Baile" y su invitación demo.

Uso:
    python manage.py crear_demo_xv_carnet
    python manage.py crear_demo_xv_carnet --host 192.168.1.50:8000

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
    help = "Crea o actualiza la invitación demo de XV años 'Carnet de Baile' (plantilla xv-carnet-02)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto desde el que se abrirá el demo (para la URL de la música).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].removeprefix("http://").removeprefix("https://").rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="xv-carnet-02",
            defaults={
                "nombre": "Carnet de Baile",
                "tipo_evento": "xv",
                "color_tema": "#F9DDE3",   # barra del navegador en el celular (rosa ballet)
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
            },
        )

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-xv-regina",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "XV Años de Regina",
                "anfitriones": "Regina",
                # hora local (TIME_ZONE = America/Mexico_City): 6:00 PM, la misa
                "fecha_evento": timezone.make_aware(datetime(2027, 3, 13, 18, 0)),
                "lugar_nombre": "Ciudad de México",
                "mensaje_bienvenida": (
                    "Quince años se bordan puntada a puntada. "
                    "Guarda una pieza para mí: quiero bailar contigo esta noche."
                ),
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": date(2027, 2, 20),
                "contenido_extra": {
                    "lugar_ceremonia_etiqueta": "Misa",
                    "lugar_ceremonia_nombre": "Templo de San Juan Bautista, Coyoacán",
                    "lugar_ceremonia_mapa_url": "https://maps.google.com/?q=San+Juan+Bautista+Coyoacan",
                    "lugar_recepcion_nombre": "Jardín Las Magnolias, Tlalpan",
                    "lugar_recepcion_mapa_url": "https://maps.google.com/?q=Tlalpan+CDMX",
                    "dresscode": "Formal en tonos neutros",
                    "dresscode_colores": ["#E9DCCB", "#C9B8A8", "#8A8F98"],
                    "padres": "Mariana Ortega & Luis Fernández",
                    "padrinos": [
                        {"rol": "Padrinos de honor", "nombres": "Claudia & Roberto Ortega"},
                        {"rol": "Padrinos de última muñeca", "nombres": "Sofía & Andrés Ruiz"},
                    ],
                    "itinerario": [
                        {"hora": "6:00 PM", "evento": "Misa de acción de gracias"},
                        {"hora": "8:00 PM", "evento": "Recepción"},
                        {"hora": "9:00 PM", "evento": "Vals"},
                        {"hora": "9:30 PM", "evento": "Cena"},
                        {"hora": "10:30 PM", "evento": "¡A la pista!"},
                    ],
                    "mesa_regalos_url": "https://mesaderegalos.liverpool.com.mx/",
                    "admite_ninos": True,
                },
                "activa": True,
            },
        )

        accion = "Creada" if creada else "Actualizada"
        self.stdout.write(self.style.SUCCESS(
            f"{accion}: http://{host}/invitaciones/{invitacion.slug}/ (plantilla {plantilla.slug_tema})"
        ))
