"""
Crea (o actualiza) la plantilla de XV años "Cajita Musical" y su invitación demo.

Uso:
    python manage.py crear_demo_xv_cajita
    python manage.py crear_demo_xv_cajita --host 192.168.1.50:8000

--host solo arma la URL absoluta de la música (musica_url es un URLField y
exige esquema + dominio). Para abrir el demo desde el iPhone por WiFi, pasa
la IP de tu compu. Acepta la IP con o sin "http://".

La foto del espejo es arte propio (la quinceañera de espaldas, con tiara, bajo
luces de jardín: sin cara, así no hay dudas de licencia ni de derechos de
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

FOTO_DEMO = Path(__file__).resolve().parents[2] / "static" / "invitaciones" / "img" / "xv-cajita-demo.jpg"


class Command(BaseCommand):
    help = "Crea o actualiza la invitación demo de XV años 'Cajita Musical' (plantilla xv-cajita-04)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto desde el que se abrirá el demo (para la URL de la música).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].removeprefix("http://").removeprefix("https://").rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="xv-cajita-04",
            defaults={
                "nombre": "Cajita Musical",
                "tipo_evento": "xv",
                "color_tema": "#380A16",   # barra del navegador en el celular (terciopelo vino)
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
            },
        )

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-xv-isabella",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "XV Años de Isabella",
                "anfitriones": "Isabella",
                # hora local (TIME_ZONE = America/Mexico_City): sábado 6:00 PM, la misa
                "fecha_evento": timezone.make_aware(datetime(2027, 11, 20, 18, 0)),
                "mensaje_bienvenida": (
                    "Hay melodías que se quedan para siempre. La mía empezó a sonar "
                    "hace quince años y quiero que estés conmigo cuando suene mi vals."
                ),
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": date(2027, 10, 30),
                "contenido_extra": {
                    "lugar_ceremonia_etiqueta": "Misa de acción de gracias",
                    "lugar_ceremonia_nombre": "Templo de Santo Domingo, Puebla",
                    "lugar_ceremonia_mapa_url": "https://www.google.com/maps/search/?api=1&query=Templo+de+Santo+Domingo+Puebla",
                    "lugar_recepcion_nombre": "Salón Versalles",
                    "lugar_recepcion_mapa_url": "https://www.google.com/maps/search/?api=1&query=Puebla+Puebla",
                    "dresscode": "Formal · tonos joya",
                    "dresscode_colores": ["#7A1C30", "#1E5B4F", "#22336B"],
                    "padres": "Ana Lucía Torres & Ricardo Morales",
                    "padrinos": [
                        {"rol": "Padrinos de honor", "nombres": "Gabriela & Andrés Torres"},
                        {"rol": "Chambelán de honor", "nombres": "Emilio Morales"},
                    ],
                    "itinerario": [
                        {"hora": "6:00 PM", "evento": "Misa de acción de gracias"},
                        {"hora": "8:00 PM", "evento": "Recepción"},
                        {"hora": "9:00 PM", "evento": "Vals"},
                        {"hora": "9:30 PM", "evento": "Cena"},
                        {"hora": "10:30 PM", "evento": "¡A bailar!"},
                    ],
                    "mesa_regalos_url": "https://mesaderegalos.liverpool.com.mx/",
                    "admite_ninos": True,
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
