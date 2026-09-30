"""
Borra las confirmaciones (RSVP) y votos de los eventos que ya pasaron hace
más de DIAS_RETENCION_DATOS días (90 por defecto).

Uso:
    python manage.py borrar_datos_vencidos --simular   # solo cuenta, no borra
    python manage.py borrar_datos_vencidos

Por qué: el aviso de privacidad promete que los datos de los invitados no
se guardan para siempre. Este comando es lo que hace verdad esa promesa;
conviene correrlo diario como tarea programada (ver DESPLIEGUE.md).
La invitación en sí (y sus fotos) no se borra: el cliente puede querer
verla de recuerdo. Para ocultarla, desmarca "activa" en el admin.
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from invitaciones.models import Confirmacion, Voto


class Command(BaseCommand):
    help = "Borra RSVP y votos de eventos que pasaron hace más de DIAS_RETENCION_DATOS días."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=settings.DIAS_RETENCION_DATOS,
                            help="Días después del evento (por defecto, DIAS_RETENCION_DATOS).")
        parser.add_argument("--simular", action="store_true", help="Solo muestra cuántos se borrarían.")

    def handle(self, *args, **opciones):
        limite = timezone.now() - timedelta(days=opciones["dias"])
        confirmaciones = Confirmacion.objects.filter(invitacion__fecha_evento__lt=limite)
        votos = Voto.objects.filter(invitacion__fecha_evento__lt=limite)
        n_conf, n_votos = confirmaciones.count(), votos.count()

        if opciones["simular"]:
            self.stdout.write(f"Se borrarían {n_conf} confirmaciones y {n_votos} votos "
                              f"de eventos anteriores al {limite:%d/%m/%Y}.")
            return
        confirmaciones.delete()
        votos.delete()
        self.stdout.write(self.style.SUCCESS(
            f"Borradas {n_conf} confirmaciones y {n_votos} votos de eventos anteriores al {limite:%d/%m/%Y}."
        ))
