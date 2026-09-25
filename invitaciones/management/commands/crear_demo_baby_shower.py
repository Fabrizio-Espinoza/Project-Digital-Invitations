from datetime import timedelta

from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from invitaciones.models import Invitacion, Plantilla


class Command(BaseCommand):
    """
    Crea (o actualiza) la plantilla "Diez Lunas" y una invitación demo de
    baby shower con todas las secciones prendidas. Sirve para enseñarla a
    clientes y para grabar el creativo de Meta Ads.

    Las fechas se calculan a partir de HOY: cada vez que lo corres, el evento
    queda a 30 días y el parto a ~12 semanas, así el countdown y las lunas
    siempre se ven "a medio camino" y nunca como un evento que ya pasó.

    Uso:  python manage.py crear_demo_baby_shower
    """

    help = "Crea/actualiza la plantilla 'Diez Lunas' y la invitación demo de baby shower."

    SLUG_DEMO = "baby-shower-demo"

    def handle(self, *args, **options):
        plantilla, _ = Plantilla.objects.update_or_create(
            slug_tema="baby-shower-lunas-01",
            defaults={
                "nombre": "Diez Lunas",
                "tipo_evento": "baby_shower",
                "soporta_rsvp": True,
                "soporta_musica": True,
                "soporta_galeria": True,
                "soporta_votacion": True,
            },
        )

        fecha_evento = (timezone.localtime() + timedelta(days=30)).replace(
            hour=17, minute=0, second=0, microsecond=0
        )
        fecha_parto = fecha_evento.date() + timedelta(days=56)

        invitacion, creada = Invitacion.objects.update_or_create(
            slug=self.SLUG_DEMO,
            defaults={
                "plantilla": plantilla,
                "nivel": "premium",
                "titulo_evento": "Baby Shower de Mariana & Diego",
                "anfitriones": "Mariana & Diego",
                "fecha_evento": fecha_evento,
                "lugar_nombre": "Jardín Las Nubes",
                "lugar_mapa_url": "https://www.google.com/maps/search/?api=1&query=Coyoac%C3%A1n%2C+CDMX",
                "mensaje_bienvenida": (
                    "Con el corazón lleno de ilusión te invitamos a celebrar la llegada "
                    "de nuestro bebé. ¡Acompáñanos a descubrir si es niña o niño!"
                ),
                "fecha_limite_rsvp": fecha_evento.date() - timedelta(days=7),
                "activa": True,
                "contenido_extra": {
                    # sin bebe_nombre a propósito: es un baby shower de revelación
                    "fecha_probable_parto": fecha_parto.isoformat(),
                    "lugar_direccion": "Av. Francisco Sosa 215, Coyoacán, CDMX",
                    "dresscode": "Rosa o azul, según tu predicción",
                    "dresscode_colores": ["#EBB7C5", "#A9C8E8"],
                    "votacion": {
                        "pregunta": "¿Niña o niño?",
                        "subtitulo": "Haz tu predicción: el gran secreto se revela el día del baby shower.",
                        "opciones": [
                            {"clave": "nina", "texto": "Niña", "color": "#E7A3B7", "revelacion": "¡Es niña!"},
                            {"clave": "nino", "texto": "Niño", "color": "#8FB8E3", "revelacion": "¡Es niño!"},
                        ],
                        "resultado": "",
                    },
                    "mesas_regalos": [
                        {
                            "nombre": "Liverpool",
                            "codigo": "51384920",
                            "url": "https://mesaderegalos.liverpool.com.mx/",
                        },
                        {
                            "nombre": "Amazon",
                            "url": "https://www.amazon.com.mx/baby-reg/homepage",
                        },
                    ],
                    "lluvia_sobres": "El día del evento habrá una cajita especial para sobres.",
                    "lluvia_panales": [
                        {"desde": "A", "hasta": "F", "talla": "Etapa 1"},
                        {"desde": "G", "hasta": "L", "talla": "Etapa 2"},
                        {"desde": "M", "hasta": "R", "talla": "Etapa 3"},
                        {"desde": "S", "hasta": "Z", "talla": "Etapa 4"},
                    ],
                },
            },
        )

        accion = "Creada" if creada else "Actualizada"
        url = reverse("invitaciones:detalle", args=[invitacion.slug])
        self.stdout.write(self.style.SUCCESS(f"{accion}: {invitacion.titulo_evento}"))
        self.stdout.write(f"  Ábrela en: http://127.0.0.1:8000{url}")
        self.stdout.write(
            '  Para revelar: en el admin pon "resultado": "nina" (o "nino") dentro de "votacion".'
        )
