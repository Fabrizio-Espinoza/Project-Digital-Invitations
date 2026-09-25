import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Invitacion, Plantilla


class MotorInvitacionesTests(TestCase):
    """
    Pruebas de punta a punta de la vista pública: arman una invitación,
    la abren como lo haría un invitado y revisan qué partes se pintan.
    """

    def crear_invitacion(self, slug_tema, tipo_evento, **datos_extra):
        plantilla, _ = Plantilla.objects.get_or_create(
            slug_tema=slug_tema,
            defaults={"nombre": slug_tema, "tipo_evento": tipo_evento},
        )
        datos = {
            "plantilla": plantilla,
            "titulo_evento": "Sofi cumple 30",
            "anfitriones": "Sofía",
            "fecha_evento": timezone.now() + datetime.timedelta(days=10),
        }
        datos.update(datos_extra)
        return Invitacion.objects.create(**datos)

    def abrir(self, invitacion):
        return self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))

    def test_plantilla_fiesta_se_pinta_completa(self):
        invitacion = self.crear_invitacion(
            "fiesta-neon-01", "fiesta",
            nivel="premium", musica_url="https://ejemplo.com/cancion.mp3",
        )
        respuesta = self.abrir(invitacion)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/fiesta-neon-01.html")
        self.assertContains(respuesta, "¡Hay fiesta!")
        self.assertContains(respuesta, 'class="disco"')
        self.assertContains(respuesta, "Sofi cumple 30")  # cinta marquesina
        self.assertContains(respuesta, 'id="boton-musica"')
        self.assertContains(respuesta, 'class="musica-pista"')
        self.assertContains(respuesta, "rsvp:enviado")  # confeti conectado al motor

    def test_frase_superior_reemplaza_el_texto_por_defecto(self):
        invitacion = self.crear_invitacion(
            "fiesta-neon-01", "fiesta",
            contenido_extra={"frase_superior": "Cumpleaños #30"},
        )
        respuesta = self.abrir(invitacion)

        self.assertContains(respuesta, "Cumpleaños #30")
        self.assertNotContains(respuesta, "¡Hay fiesta!")

    def test_lugar_unico_usa_las_columnas_del_modelo(self):
        invitacion = self.crear_invitacion(
            "fiesta-neon-01", "fiesta",
            lugar_nombre="Terraza Roma Norte",
            lugar_mapa_url="https://maps.google.com/?q=Roma+Norte",
        )
        respuesta = self.abrir(invitacion)

        self.assertContains(respuesta, "Terraza Roma Norte")
        self.assertContains(respuesta, "https://maps.google.com/?q=Roma+Norte")
        self.assertContains(respuesta, "Ubicación")

    def test_lugar_unico_no_se_duplica_si_hay_ceremonia_y_recepcion(self):
        invitacion = self.crear_invitacion(
            "boda-minimal-01", "boda",
            lugar_nombre="Lugar viejo que no debe salir",
            lugar_mapa_url="https://maps.google.com/?q=viejo",
            contenido_extra={
                "lugar_ceremonia_nombre": "Parroquia San Juan",
                "lugar_ceremonia_mapa_url": "https://maps.google.com/?q=parroquia",
            },
        )
        respuesta = self.abrir(invitacion)

        self.assertContains(respuesta, "Parroquia San Juan")
        self.assertNotContains(respuesta, "Lugar viejo que no debe salir")
        self.assertNotContains(respuesta, "https://maps.google.com/?q=viejo")

    def test_boda_sigue_funcionando_con_el_motor(self):
        invitacion = self.crear_invitacion("boda-minimal-01", "boda")
        respuesta = self.abrir(invitacion)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "¡Nos casamos!")

    def test_musica_solo_se_muestra_en_nivel_premium(self):
        invitacion = self.crear_invitacion(
            "fiesta-neon-01", "fiesta",
            nivel="interactiva", musica_url="https://ejemplo.com/cancion.mp3",
        )
        respuesta = self.abrir(invitacion)

        self.assertNotContains(respuesta, 'id="boton-musica"')
        self.assertNotContains(respuesta, 'class="musica-pista"')
