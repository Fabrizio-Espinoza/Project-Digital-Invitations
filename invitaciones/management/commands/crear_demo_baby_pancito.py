"""
Crea (o actualiza) la plantilla de baby shower "Pancito en el Horno" y su invitación demo.

Uso:
    python manage.py crear_demo_baby_pancito
    python manage.py crear_demo_baby_pancito --host 192.168.1.50:8000

--host solo arma la URL absoluta de la música (musica_url es un URLField y
exige esquema + dominio). Para abrir el demo desde el iPhone por WiFi, pasa
la IP de tu compu. Acepta la IP con o sin "http://".

Las fechas son relativas a hoy (baby shower en 30 días, parto 8 semanas
después), así la charola siempre tiene panes horneados, uno en el horno y
masa cruda. Es idempotente: correrlo varias veces actualiza el mismo registro.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from invitaciones.models import Invitacion, Plantilla


class Command(BaseCommand):
    help = "Crea o actualiza la invitación demo de baby shower 'Pancito en el Horno' (plantilla baby-shower-panaderia-03)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto desde el que se abrirá el demo (para la URL de la música).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].removeprefix("http://").removeprefix("https://").rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="baby-shower-panaderia-03",
            defaults={
                "nombre": "Pancito en el Horno",
                "tipo_evento": "baby_shower",
                "color_tema": "#F2A7BC",   # barra del navegador en el celular (concha de fresa)
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
                "soporta_votacion": True,
            },
        )

        # localtime (no now): now() viene en UTC y la hora saldria corrida
        fecha_evento = (timezone.localtime() + timedelta(days=30)).replace(
            hour=17, minute=0, second=0, microsecond=0
        )
        fecha_parto = fecha_evento.date() + timedelta(days=56)

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-baby-pancito",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Baby Shower de Fernanda & Iván",
                "anfitriones": "Fernanda & Iván",
                "fecha_evento": fecha_evento,
                "lugar_nombre": "Casa de la abuela Chelo, Tlalpan",
                "lugar_mapa_url": "https://maps.google.com/?q=Tlalpan+CDMX",
                "mensaje_bienvenida": (
                    "Nuestro pancito se está horneando a fuego lento. Antes de que "
                    "salga del horno, ven a celebrarlo con cafecito y pan dulce."
                ),
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": fecha_evento.date() - timedelta(days=7),
                "contenido_extra": {
                    # sin bebe_nombre a propósito: es un baby shower de revelación
                    "fecha_probable_parto": fecha_parto.isoformat(),
                    "lugar_direccion": "Calle Juárez 42, Centro de Tlalpan",
                    "dresscode": "Casual · colores pastel",
                    "dresscode_colores": ["#F2A7BC", "#F7E3B5", "#B8E0C2"],
                    "itinerario": [
                        {"hora": "5:00 PM", "evento": "Café, champurrado y pan"},
                        {"hora": "5:45 PM", "evento": "Juegos"},
                        {"hora": "6:30 PM", "evento": "Revelación del sabor"},
                        {"hora": "7:00 PM", "evento": "Pastel y regalos"},
                    ],
                    "admite_ninos": True,
                    "votacion": {
                        "pregunta": "¿De qué sabor viene?",
                        "subtitulo": "Concha de fresa si es niña, de chocolate si es niño. Haz tu predicción.",
                        "opciones": [
                            {"clave": "nina", "texto": "Fresa · niña", "color": "#F2A7BC", "revelacion": "¡Es niña!"},
                            {"clave": "nino", "texto": "Chocolate · niño", "color": "#7A4A33", "revelacion": "¡Es niño!"},
                        ],
                        "resultado": "",
                    },
                    "mesas_regalos": [
                        {"nombre": "Liverpool", "codigo": "51672034", "url": "https://mesaderegalos.liverpool.com.mx/"},
                        {"nombre": "Amazon", "url": "https://www.amazon.com.mx/baby-reg/homepage"},
                    ],
                    "lluvia_sobres": "El día del evento habrá una canasta de pan para los sobres.",
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

        accion = "Creada" if creada else "Actualizada"
        self.stdout.write(self.style.SUCCESS(
            f"{accion}: http://{host}/invitaciones/{invitacion.slug}/ (plantilla {plantilla.slug_tema})"
        ))
        self.stdout.write('  Para revelar: en el admin pon "resultado": "nina" (o "nino") dentro de "votacion".')
