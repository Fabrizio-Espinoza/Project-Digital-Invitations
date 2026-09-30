"""
Crea (o actualiza) la plantilla de XV años "La Gira" y su invitación demo.

Uso:
    python manage.py crear_demo_xv_gira
    python manage.py crear_demo_xv_gira --host 192.168.1.50:8000

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
    help = "Crea o actualiza la invitación demo de XV años 'La Gira' (plantilla xv-gira-03)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto desde el que se abrirá el demo (para la URL de la música).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].removeprefix("http://").removeprefix("https://").rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="xv-gira-03",
            defaults={
                "nombre": "La Gira",
                "tipo_evento": "xv",
                "color_tema": "#26143F",   # barra del navegador en el celular (la marquesina)
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
            },
        )

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-xv-ximena",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "XV Años de Ximena",
                "anfitriones": "Ximena",
                # hora local (TIME_ZONE = America/Mexico_City): sábado 6:00 PM, la misa
                "fecha_evento": timezone.make_aware(datetime(2027, 6, 12, 18, 0)),
                "mensaje_bienvenida": (
                    "Quince años ensayando para esta noche. El show es una sola "
                    "fecha y tu lugar ya está apartado."
                ),
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": date(2027, 5, 22),
                "contenido_extra": {
                    "ciudad": "Guadalajara, Jal.",
                    "lugar_ceremonia_etiqueta": "Misa",
                    "lugar_ceremonia_nombre": "Parroquia de Nuestra Señora del Carmen",
                    "lugar_ceremonia_mapa_url": "https://maps.google.com/?q=Guadalajara+Jalisco",
                    "lugar_recepcion_etiqueta": "El show",
                    "lugar_recepcion_nombre": "Salón Cristal, Zapopan",
                    "lugar_recepcion_mapa_url": "https://maps.google.com/?q=Zapopan+Jalisco",
                    "dresscode": "Formal · con un toque de brillo",
                    "dresscode_colores": ["#FFC6E5", "#C9B6FF", "#9DEFE3"],
                    "padres": "Mariana López & Daniel Ruiz",
                    "padres_etiqueta": "Mis papás",
                    "padrinos": [
                        {"rol": "Padrinos de honor", "nombres": "Paola & Ricardo López"},
                        {"rol": "Madrina de última muñeca", "nombres": "Fernanda Ruiz"},
                    ],
                    "itinerario": [
                        {"hora": "6:00 PM", "evento": "Misa de acción de gracias"},
                        {"hora": "8:00 PM", "evento": "Entrada de Ximena"},
                        {"hora": "8:30 PM", "evento": "Vals con chambelanes"},
                        {"hora": "9:15 PM", "evento": "Cena"},
                        {"hora": "10:00 PM", "evento": "Baile sorpresa"},
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
