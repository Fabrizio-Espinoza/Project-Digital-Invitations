"""
Crea (o actualiza) la plantilla de graduación "Próxima Salida" y su invitación demo.

Uso:
    python manage.py crear_demo_graduacion_salida
    python manage.py crear_demo_graduacion_salida --host 192.168.1.50:8000

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
    help = "Crea o actualiza la invitación demo de graduación 'Próxima Salida' (plantilla graduacion-salida-03)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto desde el que se abrirá el demo (para la URL de la música).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].removeprefix("http://").removeprefix("https://").rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="graduacion-salida-03",
            defaults={
                "nombre": "Próxima Salida",
                "tipo_evento": "graduacion",
                "color_tema": "#FFCB1F",   # barra del navegador en el celular (amarillo de señaletica)
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
            },
        )

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-graduacion-camila",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Graduación de Camila Torres",
                "anfitriones": "Camila Torres",
                # hora local (TIME_ZONE = America/Mexico_City): sábado 5:00 PM, la ceremonia
                "fecha_evento": timezone.make_aware(datetime(2027, 6, 19, 17, 0)),
                "lugar_nombre": "Monterrey, N.L.",
                "mensaje_bienvenida": (
                    "Después de cuatro años de clases, exámenes y desvelos, mi siguiente "
                    "vuelo está por despegar. Quiero que estés a bordo."
                ),
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": date(2027, 6, 1),
                "contenido_extra": {
                    "carrera": "Relaciones Internacionales",
                    "institucion": "Universidad Autónoma de Nuevo León",
                    "generacion": "2023 — 2027",
                    "lugar_ceremonia_etiqueta": "Ceremonia",
                    "lugar_ceremonia_nombre": "Aula Magna, Colegio Civil",
                    "lugar_ceremonia_mapa_url": "https://maps.google.com/?q=Colegio+Civil+Monterrey",
                    "lugar_recepcion_etiqueta": "Fiesta",
                    "lugar_recepcion_nombre": "Terraza Altavista, San Pedro",
                    "lugar_recepcion_mapa_url": "https://maps.google.com/?q=San+Pedro+Garza+Garcia",
                    "dresscode": "Formal",
                    "padres_etiqueta": "Capitanes: mis papás",
                    "padres": "Laura Garza & Roberto Torres",
                    "padrinos": [
                        {"rol": "Copiloto", "nombres": "Andrés Torres, mi hermano"},
                    ],
                    "itinerario": [
                        {"hora": "5:00 PM", "evento": "Ceremonia de graduación"},
                        {"hora": "7:00 PM", "evento": "Fotos con la generación"},
                        {"hora": "8:00 PM", "evento": "Cena"},
                        {"hora": "9:30 PM", "evento": "Brindis y palabras"},
                        {"hora": "10:00 PM", "evento": "¡Fiesta!"},
                    ],
                    "mesa_regalos_etiqueta": "Lluvia de sobres",
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
