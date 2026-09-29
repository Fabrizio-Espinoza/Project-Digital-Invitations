"""
Crea (o actualiza) la plantilla de baby shower "Entrega Especial" y su invitación demo.

Uso:
    python manage.py crear_demo_baby_entrega
    python manage.py crear_demo_baby_entrega --host 192.168.1.50:8000

--host solo arma la URL absoluta de la música (musica_url es un URLField y
exige esquema + dominio). Para abrir el demo desde el iPhone por WiFi, pasa
la IP de tu compu. Acepta la IP con o sin "http://".

Las fechas son relativas a hoy (baby shower en 30 días, parto 8 semanas
después), así el rastreo del envío siempre se ve "en tránsito". Es
idempotente: correrlo varias veces actualiza el mismo registro.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from invitaciones.models import Invitacion, Plantilla


class Command(BaseCommand):
    help = "Crea o actualiza la invitación demo de baby shower 'Entrega Especial' (plantilla baby-shower-entrega-02)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto desde el que se abrirá el demo (para la URL de la música).",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].removeprefix("http://").removeprefix("https://").rstrip("/")

        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="baby-shower-entrega-02",
            defaults={
                "nombre": "Entrega Especial",
                "tipo_evento": "baby_shower",
                "color_tema": "#CFA877",   # barra del navegador en el celular (carton kraft)
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
            slug="demo-baby-entrega",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Baby Shower de Andrea & Luis",
                "anfitriones": "Andrea & Luis",
                "fecha_evento": fecha_evento,
                "lugar_nombre": "Terraza Los Almendros",
                "lugar_mapa_url": "https://maps.google.com/?q=Coyoacan+CDMX",
                "mensaje_bienvenida": (
                    "Nuestro paquete más esperado ya viene en camino. "
                    "Acompáñanos a celebrar antes de que llegue."
                ),
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": fecha_evento.date() - timedelta(days=7),
                "contenido_extra": {
                    # sin bebe_nombre a propósito: es un baby shower de revelación
                    "fecha_probable_parto": fecha_parto.isoformat(),
                    "lugar_direccion": "Av. Miguel Ángel de Quevedo 350, Coyoacán",
                    "dresscode": "Casual · rosa o azul, según tu predicción",
                    "dresscode_colores": ["#F2A7B8", "#8CC7E8"],
                    "votacion": {
                        "pregunta": "¿Qué trae el paquete?",
                        "subtitulo": "Haz tu predicción: el contenido se revela el día del baby shower.",
                        "opciones": [
                            {"clave": "nina", "texto": "Niña", "color": "#F2A7B8", "revelacion": "¡Es niña!"},
                            {"clave": "nino", "texto": "Niño", "color": "#8CC7E8", "revelacion": "¡Es niño!"},
                        ],
                        "resultado": "",
                    },
                    "mesas_regalos": [
                        {"nombre": "Liverpool", "codigo": "51384920", "url": "https://mesaderegalos.liverpool.com.mx/"},
                        {"nombre": "Amazon", "url": "https://www.amazon.com.mx/baby-reg/homepage"},
                    ],
                    "lluvia_sobres": "El día del evento habrá una caja especial para sobres.",
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
