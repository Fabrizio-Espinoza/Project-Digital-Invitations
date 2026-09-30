"""
Link privado del panel del anfitrión. En tres pasos porque un campo único
con valor al azar no se puede agregar de un jalón a una tabla con filas:
Django calcularía UN solo valor y se lo daría a todas (choca el unique).
1) se agrega vacío, 2) se le da un token distinto a cada invitación,
3) se vuelve único y obligatorio.
"""
import secrets

from django.db import migrations, models

import invitaciones.models


def dar_tokens(apps, schema_editor):
    Invitacion = apps.get_model("invitaciones", "Invitacion")
    for invitacion in Invitacion.objects.filter(token_panel__isnull=True):
        invitacion.token_panel = secrets.token_urlsafe(9)
        invitacion.save(update_fields=["token_panel"])


class Migration(migrations.Migration):

    dependencies = [
        ("invitaciones", "0004_pedido"),
    ]

    operations = [
        migrations.AddField(
            model_name="invitacion",
            name="token_panel",
            field=models.CharField(max_length=24, null=True, editable=False),
        ),
        migrations.RunPython(dar_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="invitacion",
            name="token_panel",
            field=models.CharField(
                default=invitaciones.models._token_privado, editable=False, max_length=24, unique=True
            ),
        ),
    ]
