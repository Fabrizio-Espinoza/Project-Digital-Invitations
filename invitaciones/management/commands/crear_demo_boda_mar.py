"""
Crea (o actualiza) la plantilla de boda "Frente al Mar" y su invitación demo.

Uso:
    python manage.py crear_demo_boda_mar
    python manage.py crear_demo_boda_mar --host 192.168.1.50:8000

--host solo arma la URL absoluta de la música (musica_url es un URLField y
exige esquema + dominio). Para abrir el demo desde el iPhone por WiFi, pasa
la IP de tu compu. Acepta la IP con o sin "http://".

La foto de portada del demo es arte propio (los novios de espaldas en la
orilla, a contraluz, sin caras: sin dudas de licencia ni de derechos de
imagen). Vive en static y se copia a media como si la hubiera subido un
cliente, para que el demo use el mismo camino que una invitación real.

Es idempotente: correrlo varias veces actualiza el mismo registro (y la foto
solo se copia si falta).
"""
from datetime import date, datetime
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils import timezone

from invitaciones.models import Invitacion, Plantilla

FOTO_DEMO = Path(__file__).resolve().parents[2] / "static" / "invitaciones" / "img" / "boda-mar-demo.jpg"


class Command(BaseCommand):
    help = "Crea o actualiza la invitación demo de boda 'Frente al Mar' (plantilla boda-mar-05)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto desde el que se abrirá el demo (para la URL de la música).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].removeprefix("http://").removeprefix("https://").rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="boda-mar-05",
            defaults={
                "nombre": "Frente al Mar",
                "tipo_evento": "boda",
                "color_tema": "#F3C9A6",   # barra del navegador en el celular (cielo de la hora dorada)
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
            },
        )

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-boda-natalia-iker",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Boda de Natalia & Iker",
                "anfitriones": "Natalia & Iker",
                # hora local (TIME_ZONE = America/Mexico_City): sábado a las 5:00 PM, con la puesta de sol
                "fecha_evento": timezone.make_aware(datetime(2027, 11, 13, 17, 0)),
                "mensaje_bienvenida": (
                    "Nos conocimos con los pies en la arena y ahí mismo queremos decirnos "
                    "que sí. Acompáñanos cuando el sol toque el mar."
                ),
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": date(2027, 10, 1),
                "contenido_extra": {
                    "ciudad": "Tulum, Quintana Roo",
                    "lugar_ceremonia_etiqueta": "Ceremonia en la playa",
                    "lugar_ceremonia_nombre": "Playa Paraíso",
                    "lugar_ceremonia_mapa_url": "https://www.google.com/maps/search/?api=1&query=Playa+Paraiso+Tulum",
                    "lugar_recepcion_nombre": "Casa Arena · Club de playa",
                    "lugar_recepcion_mapa_url": "https://www.google.com/maps/search/?api=1&query=Tulum+Quintana+Roo",
                    "dresscode": "Formal de playa · tonos arena y mar",
                    "dresscode_colores": ["#E9D8C0", "#8FC1BE", "#E59A82"],
                    "padrinos": [
                        {"rol": "Padres de la novia", "nombres": "Claudia Ríos & Javier Méndez"},
                        {"rol": "Padres del novio", "nombres": "Elena Aguirre & Iñaki Salas"},
                    ],
                    "itinerario": [
                        {"hora": "5:00 PM", "evento": "Ceremonia frente al mar"},
                        {"hora": "6:00 PM", "evento": "Cóctel al atardecer"},
                        {"hora": "7:30 PM", "evento": "Cena bajo las estrellas"},
                        {"hora": "9:00 PM", "evento": "Primer baile y fiesta"},
                        {"hora": "1:00 AM", "evento": "Fogata y tornaboda"},
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
