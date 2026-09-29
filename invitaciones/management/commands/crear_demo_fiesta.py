from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from invitaciones.models import Invitacion, Plantilla


class Command(BaseCommand):
    """
    Crea (o actualiza) la Plantilla "Noche Neón" y una invitación de fiesta
    de ejemplo, para ver el diseño sin capturar nada a mano en el admin.

    Uso:
        python manage.py crear_demo_fiesta
        python manage.py crear_demo_fiesta --host 192.168.1.50:8000

    --host arma la URL de la música (musica_url exige una URL completa):
    con tu IP de WiFi la canción también suena al abrirla desde el iPhone.

    Es idempotente: correrlo dos veces no duplica registros. Si ya creaste
    la plantilla "fiesta-neon-01" en el admin, respeta su nombre y solo
    ajusta tipo y color.
    """

    help = "Crea la plantilla de fiesta y una invitación demo en /invitaciones/demo-fiesta/"

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto con el que abrirás la invitación (default 127.0.0.1:8000).",
        )

    def handle(self, *args, **options):
        host = options["host"]
        datos_plantilla = {
            "tipo_evento": "fiesta",
            # mismo tono que el fondo del diseño: la barra del celular y la
            # pantalla de carga de la PWA se pintan de "noche", sin flash blanco
            "color_tema": "#0E0A1A",
            "soporta_rsvp": True,
            "soporta_musica": True,
            "soporta_galeria": True,
        }
        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="fiesta-neon-01",
            defaults=datos_plantilla,
            create_defaults={"nombre": "Noche Neón", **datos_plantilla},
        )

        # fecha relativa (siempre a futuro) para que el countdown corra;
        # localtime => las 9:00 PM son hora de México, no de UTC
        fecha = (timezone.localtime() + timedelta(days=30)).replace(hour=21, minute=0, second=0, microsecond=0)

        invitacion, creada = Invitacion.objects.update_or_create(
            slug="demo-fiesta",
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Sofi cumple 30",
                "anfitriones": "Sofía",
                "fecha_evento": fecha,
                "mensaje_bienvenida": (
                    "Treinta vueltas al sol merecen una noche que no se olvide. "
                    "Ven a bailar conmigo."
                ),
                "lugar_nombre": "Terraza Roma Norte",
                "lugar_mapa_url": "https://maps.google.com/?q=Roma+Norte+CDMX",
                "musica_url": f"http://{host}/static/invitaciones/musica/cancion-boda.mp3",
                "fecha_limite_rsvp": (fecha - timedelta(days=10)).date(),
                # sin "itinerario": en una fiesta común no hay, y la plantilla
                # convierte la pantalla lima en el póster "¡Que se arme!"
                "contenido_extra": {
                    "frase_superior": "Cumpleaños #30",
                    "dresscode": "All black + un toque neón",
                    "dresscode_color": "#D6FF3D",
                    "admite_ninos": False,
                },
            },
        )

        accion = "Creada" if creada else "Actualizada"
        self.stdout.write(self.style.SUCCESS(
            f"{accion}: http://{host}/invitaciones/{invitacion.slug}/ (plantilla {plantilla.slug_tema})"
        ))
