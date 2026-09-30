"""
Crea (o actualiza) un formulario de DEMO por cada diseño del catálogo, para
mandárselo a un prospecto: "llénalo como si fuera tu evento y mira cómo
quedaría". Funciona completo pero no guarda nada (Pedido.es_demo).

Uso:
    python manage.py crear_demos_formulario
    python manage.py crear_demos_formulario --host https://invitavibra.pythonanywhere.com

Los links son fijos (/pedido/demo-<slug_tema>/), así que se pueden poner en
el catálogo o en una respuesta rápida de WhatsApp y no cambian nunca.
Necesita que las plantillas ya existan (crear_todos_los_demos las crea).
"""
from django.core.management.base import BaseCommand

from invitaciones.catalogo import DISENOS
from invitaciones.models import Pedido, Plantilla


def token_demo(slug_tema):
    return f"demo-{slug_tema}"


class Command(BaseCommand):
    help = "Crea un formulario de demo (no guarda nada) por cada diseño del catálogo."

    def add_arguments(self, parser):
        parser.add_argument("--host", default="127.0.0.1:8000", help="Solo para imprimir los links.")

    def handle(self, *args, **opciones):
        host = opciones["host"].rstrip("/")
        if not host.startswith(("http://", "https://")):
            host = "http://" + host
        plantillas = {p.slug_tema: p for p in Plantilla.objects.filter(slug_tema__in=[d["slug_tema"] for d in DISENOS])}
        for diseno in DISENOS:
            plantilla = plantillas.get(diseno["slug_tema"])
            if plantilla is None:
                self.stdout.write(f"  (sin plantilla {diseno['slug_tema']}: corre crear_todos_los_demos)")
                continue
            pedido, _ = Pedido.objects.update_or_create(
                token=token_demo(diseno["slug_tema"]),
                defaults={
                    "cliente": f"Demo del formulario · {diseno['nombre']}",
                    "plantilla": plantilla,
                    "nivel": "premium",       # que se vean todas las preguntas
                    "es_demo": True,
                },
            )
            self.stdout.write(f"  {diseno['nombre']:<22} {host}/pedido/{pedido.token}/")
