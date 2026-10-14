"""
Crea (o actualiza) la plantilla de graduación "Mención Honorífica" y su invitación demo.

Uso:
    python manage.py crear_demo_graduacion_tesis
    python manage.py crear_demo_graduacion_tesis --host 192.168.1.50:8000

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
    help = "Crea o actualiza la invitación demo de graduación 'Mención Honorífica' (plantilla graduacion-tesis-04)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto desde el que se abrirá el demo (para la URL de la música).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].removeprefix("http://").removeprefix("https://").rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="graduacion-tesis-04",
            defaults={
                "nombre": "Mención Honorífica",
                "tipo_evento": "graduacion",
                "color_tema": "#4E1720",   # barra del navegador en el celular (la piel vino de la tapa)
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
            },
        )

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-graduacion-fernando",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Graduación de Fernando Ibarra Solís",
                "anfitriones": "Fernando Ibarra Solís",
                # hora local (TIME_ZONE = America/Mexico_City): sábado 6:00 PM, la ceremonia
                "fecha_evento": timezone.make_aware(datetime(2027, 6, 26, 18, 0)),
                "mensaje_bienvenida": (
                    "Cinco años de códigos, desvelos y exámenes se cierran con este capítulo. "
                    "Nada de esto habría sido posible sin ti: acompáñame a celebrarlo."
                ),
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": date(2027, 6, 5),
                "contenido_extra": {
                    "carrera": "Licenciatura en Derecho",
                    "institucion": "Benemérita Universidad Autónoma de Puebla",
                    "generacion": "2022 — 2027",
                    "titulo_tesis": "De las aulas al foro: memoria de un sueño cumplido",
                    "lugar_ceremonia_etiqueta": "Ceremonia",
                    "lugar_ceremonia_nombre": "Complejo Cultural Universitario",
                    "lugar_ceremonia_mapa_url": "https://www.google.com/maps/search/?api=1&query=Complejo+Cultural+Universitario+Puebla",
                    "lugar_recepcion_etiqueta": "Cena de gala",
                    "lugar_recepcion_nombre": "Hacienda San Bartolo, Cholula",
                    "lugar_recepcion_mapa_url": "https://www.google.com/maps/search/?api=1&query=San+Pedro+Cholula+Puebla",
                    "dresscode": "Etiqueta rigurosa",
                    "padres_etiqueta": "A mis padres",
                    "padres": "Patricia Solís & Fernando Ibarra",
                    "padrinos": [
                        {"rol": "Padrinos de graduación", "nombres": "Lic. Gabriela Ruiz & Lic. Tomás Peña"},
                    ],
                    "itinerario": [
                        {"hora": "4:00 PM", "evento": "Misa de acción de gracias"},
                        {"hora": "6:00 PM", "evento": "Ceremonia de graduación"},
                        {"hora": "8:00 PM", "evento": "Cóctel de bienvenida"},
                        {"hora": "9:00 PM", "evento": "Cena de gala"},
                        {"hora": "10:30 PM", "evento": "Baile"},
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
