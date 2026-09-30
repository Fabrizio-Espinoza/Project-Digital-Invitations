"""
Crea (o actualiza) TODOS los demos de un jalón y te imprime la lista de
links para abrirlos en el celular.

Uso:
    python manage.py crear_todos_los_demos --host 192.168.100.18:8000
    python manage.py crear_todos_los_demos --host https://algo.trycloudflare.com

--host solo sirve para imprimir los links: la música ya no depende de la IP
(ver Invitacion.musica_src). Es idempotente: se puede correr las veces que sea.
"""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand

# (comando, slug del demo, nombre de la plantilla) en el orden del catálogo
DEMOS = [
    ("crear_demo_terracota", "demo-boda-daniela-andres", "Boda · Terracota Velada"),
    ("crear_demo_cobalto", "demo-cobalto-editorial", "Boda · Cobalto Editorial"),
    ("crear_demo_hotel", "demo-hotel-amor", "Boda · Hotel Amor"),
    ("crear_demo_xv", "demo-xv-valentina", "XV · Medianoche Dorada"),
    ("crear_demo_xv_carnet", "demo-xv-regina", "XV · Carnet de Baile"),
    ("crear_demo_xv_gira", "demo-xv-ximena", "XV · La Gira"),
    ("crear_demo_graduacion", "demo-graduacion-valeria-montes", "Graduación · Laurel de Oro"),
    ("crear_demo_graduacion_cuaderno", "demo-graduacion-diego", "Graduación · Tarea Cumplida"),
    ("crear_demo_graduacion_salida", "demo-graduacion-camila", "Graduación · Próxima Salida"),
    ("crear_demo_fiesta", "demo-fiesta-sofia", "Fiesta · Noche Neón"),
    ("crear_demo_loteria", "demo-loteria-lupita", "Fiesta · La Lotería"),
    ("crear_demo_fiesta_consola", "demo-fiesta-rodrigo", "Fiesta · Nivel Desbloqueado"),
    ("crear_demo_baby_shower", "demo-baby-mariana-diego", "Baby shower · Diez Lunas"),
    ("crear_demo_baby_entrega", "demo-baby-entrega", "Baby shower · Entrega Especial"),
    ("crear_demo_baby_pancito", "demo-baby-pancito", "Baby shower · Pancito en el Horno"),
]


class Command(BaseCommand):
    help = "Crea o actualiza todos los demos y muestra sus links."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="IP:puerto (o https://dominio del túnel) con que abrirás los demos.",
        )

    def handle(self, *args, **opciones):
        host = opciones["host"].rstrip("/")
        if not host.startswith(("http://", "https://")):
            host = "http://" + host

        self.stdout.write(self.style.SUCCESS(f"Demos listos ({len(DEMOS)}):"))
        for comando, slug, nombre in DEMOS:
            call_command(comando, stdout=StringIO())   # su propio mensaje no hace falta aquí
            self.stdout.write(f"  {nombre:<36} {host}/invitaciones/{slug}/")
