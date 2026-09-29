"""
Crea (o actualiza) la plantilla de fiesta "La Lotería" y su invitación demo.

Uso:
    python manage.py crear_demo_loteria
    python manage.py crear_demo_loteria --host 192.168.1.50:8000

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
    help = "Crea o actualiza la invitación demo de fiesta 'La Lotería' (plantilla fiesta-loteria-02)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto desde el que se abrirá el demo (para la URL de la música).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].removeprefix("http://").removeprefix("https://").rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="fiesta-loteria-02",
            defaults={
                "nombre": "La Lotería",
                "tipo_evento": "fiesta",
                "color_tema": "#F6EFE0",   # barra del navegador en el celular (papel crema)
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
            },
        )

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-loteria-lupita",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Los 80 de Lupita",
                "anfitriones": "Lupita",
                # hora local (TIME_ZONE = America/Mexico_City): comida de domingo a las 2:00 PM
                "fecha_evento": timezone.make_aware(datetime(2026, 11, 15, 14, 0)),
                "lugar_nombre": "Casa de la familia Hernández",
                "lugar_mapa_url": "https://maps.google.com/?q=Coyoacan+CDMX",
                "mensaje_bienvenida": (
                    "Ochenta años de risas, recetas y consejos. Ven a celebrar a la "
                    "abuela como se debe: con mole, mariachi y lotería."
                ),
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": date(2026, 11, 1),
                "contenido_extra": {
                    "carta_numero": "80",
                    "carta_titulo": "La Cumpleañera",
                    "carta_dibujo": "pastel",
                    "lugar_direccion": "Francisco Sosa 120, Coyoacán",
                    "dresscode": "Casual · ¡trae sombrero!",
                    "itinerario": [
                        {"hora": "2:00 PM", "evento": "Llegada y botanas"},
                        {"hora": "3:00 PM", "evento": "Comida (¡hay mole!)"},
                        {"hora": "5:00 PM", "evento": "Mañanitas y pastel"},
                        {"hora": "6:00 PM", "evento": "Lotería con premios"},
                        {"hora": "7:00 PM", "evento": "Mariachi y baile"},
                    ],
                    "admite_ninos": True,
                },
                "activa": True,
            },
        )

        accion = "Creada" if creada else "Actualizada"
        self.stdout.write(self.style.SUCCESS(
            f"{accion}: http://{host}/invitaciones/{invitacion.slug}/ (plantilla {plantilla.slug_tema})"
        ))
