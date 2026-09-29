"""
Crea (o actualiza) la plantilla de graduación "Tarea Cumplida" y su invitación demo.

Uso:
    python manage.py crear_demo_graduacion_cuaderno
    python manage.py crear_demo_graduacion_cuaderno --host 192.168.1.50:8000

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
    help = "Crea o actualiza la invitación demo de graduación 'Tarea Cumplida' (plantilla graduacion-cuaderno-02)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto desde el que se abrirá el demo (para la URL de la música).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].removeprefix("http://").removeprefix("https://").rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="graduacion-cuaderno-02",
            defaults={
                "nombre": "Tarea Cumplida",
                "tipo_evento": "graduacion",
                "color_tema": "#FBFAF5",   # barra del navegador en el celular (papel)
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
            },
        )

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-graduacion-diego",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Graduación de Diego Ramírez",
                "anfitriones": "Diego Ramírez",
                # hora local (TIME_ZONE = America/Mexico_City): 5:00 PM, la ceremonia
                "fecha_evento": timezone.make_aware(datetime(2026, 12, 5, 17, 0)),
                "lugar_nombre": "Ciudad de México",
                "mensaje_bienvenida": (
                    "Cinco años de desvelos, exámenes y cafés de máquina. "
                    "Hoy cierro este cuaderno y quiero celebrarlo contigo."
                ),
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": date(2026, 11, 21),
                "contenido_extra": {
                    "carrera": "Ingeniería Mecatrónica",
                    "institucion": "Instituto Politécnico Nacional",
                    "generacion": "2021 — 2026",
                    "lugar_ceremonia_etiqueta": "Ceremonia",
                    "lugar_ceremonia_nombre": "Auditorio Alejo Peralta, Zacatenco",
                    "lugar_ceremonia_mapa_url": "https://maps.google.com/?q=Auditorio+Alejo+Peralta+IPN",
                    "lugar_recepcion_etiqueta": "Fiesta",
                    "lugar_recepcion_nombre": "Salón Los Arcos, Lindavista",
                    "lugar_recepcion_mapa_url": "https://maps.google.com/?q=Lindavista+CDMX",
                    "dresscode": "Formal",
                    "padres_etiqueta": "Gracias a mis papás",
                    "padres": "Rosa María López & Jorge Ramírez",
                    "itinerario": [
                        {"hora": "5:00 PM", "evento": "Ceremonia de graduación"},
                        {"hora": "7:00 PM", "evento": "Fotos con la generación"},
                        {"hora": "8:00 PM", "evento": "Cena"},
                        {"hora": "9:30 PM", "evento": "Brindis"},
                        {"hora": "10:00 PM", "evento": "¡Fiesta!"},
                    ],
                    "mesa_regalos_etiqueta": "Lluvia de sobres",
                    "mesa_regalos_url": "https://mesaderegalos.liverpool.com.mx/",
                },
                "activa": True,
            },
        )

        accion = "Creada" if creada else "Actualizada"
        self.stdout.write(self.style.SUCCESS(
            f"{accion}: http://{host}/invitaciones/{invitacion.slug}/ (plantilla {plantilla.slug_tema})"
        ))
