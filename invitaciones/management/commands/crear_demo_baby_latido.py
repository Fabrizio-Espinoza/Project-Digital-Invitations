"""
Crea (o actualiza) la plantilla de baby shower "Primer Latido" y su invitación demo.

Uso:
    python manage.py crear_demo_baby_latido
    python manage.py crear_demo_baby_latido --host 192.168.1.50:8000

--host solo arma la URL absoluta de la música (musica_url es un URLField y
exige esquema + dominio). Para abrir el demo desde el iPhone por WiFi, pasa
la IP de tu compu. Acepta la IP con o sin "http://".

El ultrasonido del demo está DIBUJADO desde cero (abanico, moteado y un bebé
de perfil): un eco real es un dato de salud de alguien y trae impreso su
nombre y su clínica. Vive en static y se copia a media como si lo hubiera
subido un cliente.

Las fechas son relativas a hoy (baby shower en 30 días, parto 10 semanas
después), así la línea de latidos siempre va a media espera. Es idempotente:
correrlo varias veces actualiza el mismo registro (y el eco solo se copia si falta).
"""
from datetime import timedelta
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils import timezone

from invitaciones.models import Invitacion, Plantilla

FOTO_DEMO = Path(__file__).resolve().parents[2] / "static" / "invitaciones" / "img" / "baby-shower-latido-demo.jpg"


class Command(BaseCommand):
    help = "Crea o actualiza la invitación demo de baby shower 'Primer Latido' (plantilla baby-shower-latido-04)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto desde el que se abrirá el demo (para la URL de la música).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].removeprefix("http://").removeprefix("https://").rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="baby-shower-latido-04",
            defaults={
                "nombre": "Primer Latido",
                "tipo_evento": "baby_shower",
                "color_tema": "#FBF6EE",   # barra del navegador en el celular (crema del cuarto)
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
                "soporta_votacion": True,
            },
        )

        # localtime (no now): now() viene en UTC y la hora saldria corrida
        fecha_evento = (timezone.localtime() + timedelta(days=30)).replace(
            hour=16, minute=0, second=0, microsecond=0
        )
        fecha_parto = fecha_evento.date() + timedelta(days=70)

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-baby-andrea-pablo",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Baby Shower de Andrea & Pablo",
                "anfitriones": "Andrea & Pablo",
                "fecha_evento": fecha_evento,
                "lugar_nombre": "Casa Jardín Los Olivos, Querétaro",
                "lugar_mapa_url": "https://www.google.com/maps/search/?api=1&query=Centro+Queretaro",
                "mensaje_bienvenida": (
                    "Hace unas semanas escuchamos su corazón por primera vez y desde "
                    "entonces contamos los días. Ven a celebrarlo con nosotros."
                ),
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": fecha_evento.date() - timedelta(days=7),
                "contenido_extra": {
                    # sin bebe_nombre a propósito: hay votación de "¿niña o niño?"
                    "fecha_probable_parto": fecha_parto.isoformat(),
                    "lugar_direccion": "Av. Zaragoza 120, Centro",
                    "dresscode": "Casual · tonos menta y durazno",
                    "dresscode_colores": ["#6FD8C3", "#F9C9B4"],
                    "itinerario": [
                        {"hora": "4:00 PM", "evento": "Bienvenida"},
                        {"hora": "4:45 PM", "evento": "Juegos"},
                        {"hora": "5:30 PM", "evento": "¡Revelación!"},
                        {"hora": "6:00 PM", "evento": "Pastel y regalos"},
                    ],
                    "admite_ninos": True,
                    "votacion": {
                        "pregunta": "¿Niña o niño?",
                        "subtitulo": "El eco ya lo sabe… ¿y tú? Haz tu predicción.",
                        "opciones": [
                            {"clave": "nina", "texto": "Niña", "color": "#F4A3B5", "revelacion": "¡Es niña!"},
                            {"clave": "nino", "texto": "Niño", "color": "#8EC5EC", "revelacion": "¡Es niño!"},
                        ],
                        "resultado": "",
                    },
                    "mesas_regalos": [
                        {"nombre": "Liverpool", "codigo": "51803326", "url": "https://mesaderegalos.liverpool.com.mx/"},
                        {"nombre": "Amazon", "url": "https://www.amazon.com.mx/baby-reg/homepage"},
                    ],
                    "lluvia_sobres": "El día del evento habrá un buzón para los sobres.",
                    "lluvia_panales": [
                        {"desde": "A", "hasta": "F", "talla": "Etapa 1"},
                        {"desde": "G", "hasta": "L", "talla": "Etapa 2"},
                        {"desde": "M", "hasta": "R", "talla": "Etapa 3"},
                        {"desde": "S", "hasta": "Z", "talla": "Etapa 4"},
                    ],
                },
                "activa": True,
            },
        )

        # el eco se copia a media solo si falta (en la base o en el disco)
        foto = invitacion.foto_portada
        if not foto or not foto.storage.exists(foto.name):
            with FOTO_DEMO.open("rb") as archivo:
                invitacion.foto_portada.save("eco.jpg", File(archivo), save=True)

        accion = "Creada" if creada else "Actualizada"
        self.stdout.write(self.style.SUCCESS(
            f"{accion}: http://{host}/invitaciones/{invitacion.slug}/ (plantilla {plantilla.slug_tema})"
        ))
        self.stdout.write('  Para revelar: en el admin pon "resultado": "nina" (o "nino") dentro de "votacion".')
