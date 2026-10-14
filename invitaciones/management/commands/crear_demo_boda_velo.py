"""
Crea (o actualiza) la plantilla de boda "El Velo" y su invitación demo.

Uso:
    python manage.py crear_demo_boda_velo
    python manage.py crear_demo_boda_velo --host 192.168.1.50:8000

--host solo arma la URL absoluta de la música (musica_url es un URLField y
exige esquema + dominio). Para abrir el demo desde el iPhone por WiFi, pasa
la IP de tu compu. Acepta la IP con o sin "http://".

La foto de portada del demo es arte propio (novios a contraluz, sin caras:
sin dudas de licencia ni de derechos de imagen). Vive en static y se copia a
media como si la hubiera subido un cliente, para que el demo use el mismo
camino que una invitación real.

Es idempotente: correrlo varias veces actualiza el mismo registro (y la foto
solo se copia si falta).
"""
from datetime import date, datetime
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils import timezone

from invitaciones.models import Invitacion, Plantilla

FOTO_DEMO = Path(__file__).resolve().parents[2] / "static" / "invitaciones" / "img" / "boda-velo-demo.jpg"


class Command(BaseCommand):
    help = "Crea o actualiza la invitación demo de boda 'El Velo' (plantilla boda-velo-04)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto desde el que se abrirá el demo (para la URL de la música).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].removeprefix("http://").removeprefix("https://").rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="boda-velo-04",
            defaults={
                "nombre": "El Velo",
                "tipo_evento": "boda",
                "color_tema": "#F7F3EE",   # barra del navegador en el celular (marfil del tul)
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
            },
        )

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-boda-renata-tomas",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Boda de Renata & Tomás",
                "anfitriones": "Renata & Tomás",
                # hora local (TIME_ZONE = America/Mexico_City): sábado a las 5:30 PM
                "fecha_evento": timezone.make_aware(datetime(2027, 10, 16, 17, 30)),
                "mensaje_bienvenida": (
                    "Hay amores que se esperan toda la vida. El nuestro llegó, "
                    "y queremos que estés ahí el día en que nos digamos que sí."
                ),
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": date(2027, 9, 15),
                "contenido_extra": {
                    "lugar_ceremonia_etiqueta": "Ceremonia religiosa",
                    "lugar_ceremonia_nombre": "Parroquia de San Miguel Arcángel",
                    "lugar_ceremonia_mapa_url": "https://www.google.com/maps/search/?api=1&query=Parroquia+de+San+Miguel+Arcangel+San+Miguel+de+Allende",
                    "lugar_recepcion_nombre": "Hacienda Las Jacarandas",
                    "lugar_recepcion_mapa_url": "https://www.google.com/maps/search/?api=1&query=San+Miguel+de+Allende",
                    "dresscode": "Formal · tonos tierra y malva",
                    "dresscode_colores": ["#B4868D", "#CDB89D"],
                    "padrinos": [
                        {"rol": "Padres de la novia", "nombres": "Lucía Herrera & Andrés Villaseñor"},
                        {"rol": "Padres del novio", "nombres": "Carmen Ibarra & Tomás Ruiz"},
                        {"rol": "Padrinos de velación", "nombres": "Mariana & Diego Lozano"},
                    ],
                    "itinerario": [
                        {"hora": "5:30 PM", "evento": "Ceremonia religiosa"},
                        {"hora": "7:00 PM", "evento": "Cóctel en el jardín"},
                        {"hora": "8:30 PM", "evento": "Cena"},
                        {"hora": "10:00 PM", "evento": "Vals y fiesta"},
                        {"hora": "1:30 AM", "evento": "Tornaboda con chilaquiles"},
                    ],
                    "mesa_regalos_url": "https://mesaderegalos.liverpool.com.mx/",
                    "admite_ninos": False,
                },
                "activa": True,
            },
        )

        # la foto se copia a media solo si falta (en la base o en el disco)
        foto = invitacion.foto_portada
        if not foto or not foto.storage.exists(foto.name):
            with FOTO_DEMO.open("rb") as archivo:
                invitacion.foto_portada.save("portada.jpg", File(archivo), save=True)

        accion = "Creada" if creada else "Actualizada"
        self.stdout.write(self.style.SUCCESS(
            f"{accion}: http://{host}/invitaciones/{invitacion.slug}/ (plantilla {plantilla.slug_tema})"
        ))
