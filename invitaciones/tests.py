import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Invitacion, Plantilla, Voto


def config_votacion(resultado=""):
    return {
        "pregunta": "¿Niña o niño?",
        "opciones": [
            {"clave": "nina", "texto": "Niña", "color": "#E7A3B7", "revelacion": "¡Es niña!"},
            {"clave": "nino", "texto": "Niño", "color": "#8FB8E3", "revelacion": "¡Es niño!"},
        ],
        "resultado": resultado,
    }


class BabyShowerTests(TestCase):
    def setUp(self):
        self.plantilla = Plantilla.objects.create(
            nombre="Diez Lunas",
            tipo_evento="baby_shower",
            slug_tema="baby-shower-lunas-01",
            soporta_votacion=True,
        )
        self.invitacion = Invitacion.objects.create(
            slug="baby-test",
            plantilla=self.plantilla,
            nivel="premium",
            titulo_evento="Baby Shower de Mariana & Diego",
            anfitriones="Mariana & Diego",
            # 5:00 PM hora del centro de México
            fecha_evento=datetime(2026, 12, 12, 17, 0, tzinfo=ZoneInfo("America/Mexico_City")),
            lugar_nombre="Jardín Las Nubes",
            contenido_extra={
                "fecha_probable_parto": "2027-02-06",
                "votacion": config_votacion(),
                "mesas_regalos": [{"nombre": "Liverpool", "codigo": "51384920"}],
                "lluvia_panales": [{"desde": "A", "hasta": "M", "talla": "Etapa 1"}],
            },
        )

    def votar(self, opcion):
        return self.client.post(
            reverse("invitaciones:votar", args=[self.invitacion.slug]),
            data=json.dumps({"opcion": opcion}),
            content_type="application/json",
        )

    # --- Página pública ---

    def test_pinta_secciones_de_baby_shower_y_no_las_de_boda(self):
        respuesta = self.client.get(reverse("invitaciones:detalle", args=[self.invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/baby-shower-lunas-01.html")
        for fragmento in ('id="dulce-espera"', 'id="votacion"', 'id="regalos"', 'id="panales"', "Baby Shower"):
            self.assertContains(respuesta, fragmento)
        self.assertNotContains(respuesta, "Itinerario")
        self.assertNotContains(respuesta, "Ceremonia")

    def test_votacion_solo_en_premium(self):
        self.invitacion.nivel = "interactiva"
        self.invitacion.save()
        respuesta = self.client.get(reverse("invitaciones:detalle", args=[self.invitacion.slug]))
        self.assertNotContains(respuesta, 'id="votacion"')
        self.assertEqual(self.votar("nina").status_code, 404)

    def test_votacion_solo_si_la_plantilla_la_soporta(self):
        self.plantilla.soporta_votacion = False
        self.plantilla.save()
        respuesta = self.client.get(reverse("invitaciones:detalle", args=[self.invitacion.slug]))
        self.assertNotContains(respuesta, 'id="votacion"')
        self.assertEqual(self.votar("nina").status_code, 404)

    # --- Votación en vivo ---

    def test_votar_suma_y_regresa_conteos(self):
        self.votar("nino")
        respuesta = self.votar("nina")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.json(),
            {"ok": True, "conteos": {"nina": 1, "nino": 1}, "total": 2, "resultado": ""},
        )

    def test_opcion_que_no_existe_se_rechaza(self):
        respuesta = self.votar("gemelos")
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(Voto.objects.count(), 0)

    def test_cuerpo_invalido_se_rechaza_sin_error_500(self):
        for cuerpo in ("no es json", "[]", '{"opcion": ["nina"]}', "{}"):
            respuesta = self.client.post(
                reverse("invitaciones:votar", args=[self.invitacion.slug]),
                data=cuerpo,
                content_type="application/json",
            )
            self.assertEqual(respuesta.status_code, 400, cuerpo)
        self.assertEqual(Voto.objects.count(), 0)

    def test_revelar_cierra_la_votacion_y_el_conteo_trae_el_resultado(self):
        self.votar("nina")
        self.invitacion.contenido_extra["votacion"] = config_votacion(resultado="nina")
        self.invitacion.save()

        self.assertEqual(self.votar("nino").status_code, 400)
        conteo = self.client.get(reverse("invitaciones:conteo_votos", args=[self.invitacion.slug])).json()
        self.assertEqual(conteo, {"conteos": {"nina": 1, "nino": 0}, "total": 1, "resultado": "nina"})

    def test_votos_de_opciones_eliminadas_no_cuentan(self):
        Voto.objects.create(invitacion=self.invitacion, opcion="vieja")
        self.votar("nina")
        conteo = self.client.get(reverse("invitaciones:conteo_votos", args=[self.invitacion.slug])).json()
        self.assertEqual(conteo["total"], 1)

    # --- Calendario ---

    def test_calendario_ics_con_hora_de_mexico_en_utc(self):
        respuesta = self.client.get(reverse("invitaciones:calendario", args=[self.invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "text/calendar; charset=utf-8")
        contenido = respuesta.content.decode("utf-8")
        # 5:00 PM en CDMX (UTC-6) = 23:00 UTC; 4 horas de duración
        self.assertIn("DTSTART:20261212T230000Z", contenido)
        self.assertIn("DTEND:20261213T030000Z", contenido)
        self.assertIn("SUMMARY:Baby Shower de Mariana & Diego", contenido)
        self.assertIn("LOCATION:Jardín Las Nubes", contenido)
        self.assertTrue(all(len(linea.encode("utf-8")) <= 75 for linea in contenido.split("\r\n")))


class BodaSigueFuncionandoTests(TestCase):
    """La plantilla de boda no estiliza las secciones nuevas: no deben aparecer."""

    def test_boda_renderiza_sin_secciones_de_baby_shower(self):
        plantilla = Plantilla.objects.create(
            nombre="Terracota Velada", tipo_evento="boda", slug_tema="boda-minimal-01"
        )
        invitacion = Invitacion.objects.create(
            slug="boda-test",
            plantilla=plantilla,
            nivel="premium",
            titulo_evento="Boda de Ana & Luis",
            anfitriones="Ana & Luis",
            fecha_evento=timezone.now() + timedelta(days=90),
            contenido_extra={
                "lugar_ceremonia_nombre": "Parroquia San Juan",
                "itinerario": [{"hora": "5:00 PM", "evento": "Ceremonia"}],
                "votacion": config_votacion(),
            },
        )
        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "¡Nos casamos!")
        self.assertContains(respuesta, "Itinerario")
        self.assertNotContains(respuesta, 'id="votacion"')
        self.assertNotContains(respuesta, 'id="dulce-espera"')
