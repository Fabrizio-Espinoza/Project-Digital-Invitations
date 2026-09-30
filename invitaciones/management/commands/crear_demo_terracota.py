"""
Crea (o actualiza) la plantilla "Terracota Velada" y su invitación demo.

Uso:
    python manage.py crear_demo_terracota
    python manage.py crear_demo_terracota --host 192.168.1.50:8000

Terracota fue la primera plantilla y su demo se armó a mano en el admin;
este comando la vuelve reproducible como las demás (así también existe en
el servidor, que arranca con la base vacía).

Es idempotente: correrlo dos veces actualiza el mismo registro en vez de
duplicarlo (update_or_create busca por slug_tema / slug).
"""
from datetime import date, datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from invitaciones.models import Invitacion, Plantilla


class Command(BaseCommand):
    help = "Crea o actualiza la invitación demo de la plantilla Terracota Velada."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto con que abrirás el demo (solo para imprimir el link y armar musica_url).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].removeprefix("http://").removeprefix("https://").rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="boda-minimal-01",
            defaults={
                "nombre": "Terracota Velada",
                "tipo_evento": "boda",
                "color_tema": "#FBF6F0",   # barra del navegador en el celular (papel crema)
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
            },
        )

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-boda-daniela-andres",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Boda de Daniela & Andrés",
                "anfitriones": "Daniela & Andrés",
                # hora local (TIME_ZONE = America/Mexico_City): sábado a las 5:00 PM
                "fecha_evento": timezone.make_aware(datetime(2027, 3, 13, 17, 0)),
                "mensaje_bienvenida": (
                    "Con la alegría de nuestras familias, queremos compartir contigo "
                    "el día en que unimos nuestras vidas. Tu presencia es nuestro "
                    "mejor regalo."
                ),
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": date(2027, 2, 13),
                "contenido_extra": {
                    "lugar_ceremonia_nombre": "Parroquia de San Pedro Apóstol, Tlaquepaque",
                    "lugar_ceremonia_mapa_url": "https://maps.google.com/?q=Parroquia+San+Pedro+Tlaquepaque",
                    "lugar_recepcion_nombre": "Jardín Casa Terracota, Tlaquepaque",
                    "lugar_recepcion_mapa_url": "https://maps.google.com/?q=Tlaquepaque+Jalisco",
                    "dresscode": "Formal · tonos tierra bienvenidos",
                    "dresscode_color": "#C0694A",
                    "padrinos": [
                        {"rol": "Padres de la novia", "nombres": "Patricia Ruiz & Fernando Ochoa"},
                        {"rol": "Padres del novio", "nombres": "Leticia Navarro & Héctor Salas"},
                    ],
                    "itinerario": [
                        {"hora": "5:00 PM", "evento": "Ceremonia religiosa"},
                        {"hora": "6:30 PM", "evento": "Cóctel en el jardín"},
                        {"hora": "8:00 PM", "evento": "Cena"},
                        {"hora": "9:30 PM", "evento": "Primer baile y fiesta"},
                        {"hora": "1:00 AM", "evento": "Tornaboda"},
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
