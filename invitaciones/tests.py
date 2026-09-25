import json
from datetime import datetime, timedelta
from io import StringIO
from zoneinfo import ZoneInfo

from django.core.management import call_command
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
            "fecha_evento": timezone.now() + timedelta(days=10),
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

    def test_itinerario_solo_aparece_si_viene_en_el_json(self):
        sin_itinerario = self.crear_invitacion(
            "fiesta-neon-01", "fiesta",
            contenido_extra={"admite_ninos": False},
        )
        con_itinerario = self.crear_invitacion(
            "fiesta-neon-01", "fiesta",
            contenido_extra={"itinerario": [{"hora": "9:00 PM", "evento": "Llegada"}]},
        )

        self.assertNotContains(self.abrir(sin_itinerario), "<h3>Itinerario</h3>")
        self.assertContains(self.abrir(con_itinerario), "<h3>Itinerario</h3>")

    def test_musica_solo_se_muestra_en_nivel_premium(self):
        invitacion = self.crear_invitacion(
            "fiesta-neon-01", "fiesta",
            nivel="interactiva", musica_url="https://ejemplo.com/cancion.mp3",
        )
        respuesta = self.abrir(invitacion)

        self.assertNotContains(respuesta, 'id="boton-musica"')
        self.assertNotContains(respuesta, 'class="musica-pista"')


class PWATests(TestCase):
    def setUp(self):
        self.plantilla = Plantilla.objects.create(
            nombre="Terracota Velada",
            tipo_evento="boda",
            slug_tema="boda-minimal-01",
            color_tema="#FBF6F0",
        )
        self.invitacion = Invitacion.objects.create(
            slug="ana-y-luis",
            plantilla=self.plantilla,
            titulo_evento="Boda de Ana & Luis",
            anfitriones="Ana & Luis",
            fecha_evento=timezone.now() + timedelta(days=30),
        )

    def test_manifest_propio_de_la_invitacion(self):
        respuesta = self.client.get("/invitaciones/ana-y-luis/manifest.webmanifest")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/manifest+json")
        manifest = respuesta.json()
        self.assertEqual(manifest["name"], "Boda de Ana & Luis")
        self.assertEqual(manifest["short_name"], "Ana & Luis")
        self.assertEqual(manifest["start_url"], "/invitaciones/ana-y-luis/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["theme_color"], "#FBF6F0")
        self.assertIn("/static/invitaciones/pwa/boda-minimal-01-512.png", [i["src"] for i in manifest["icons"]])

    def test_icono_default_si_la_plantilla_no_tiene_propio(self):
        self.plantilla.slug_tema = "xv-nueva"
        self.plantilla.save()
        manifest = self.client.get("/invitaciones/ana-y-luis/manifest.webmanifest").json()
        self.assertIn("/static/invitaciones/pwa/default-512.png", [i["src"] for i in manifest["icons"]])

    def test_manifest_de_invitacion_inactiva_da_404(self):
        self.invitacion.activa = False
        self.invitacion.save()
        respuesta = self.client.get("/invitaciones/ana-y-luis/manifest.webmanifest")
        self.assertEqual(respuesta.status_code, 404)

    def test_service_worker_se_sirve_como_javascript(self):
        respuesta = self.client.get("/invitaciones/sw.js")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/javascript")
        self.assertEqual(respuesta["Cache-Control"], "no-cache")

    def test_la_invitacion_enlaza_manifest_e_iconos(self):
        respuesta = self.client.get("/invitaciones/ana-y-luis/")
        self.assertContains(respuesta, 'href="/invitaciones/ana-y-luis/manifest.webmanifest"')
        self.assertContains(respuesta, '<meta name="theme-color" content="#FBF6F0">')
        self.assertContains(respuesta, "/static/invitaciones/pwa/boda-minimal-01-180.png")
        self.assertContains(respuesta, 'register("/invitaciones/sw.js")')


class DemoFiestaTests(TestCase):
    def test_crear_demo_fiesta_es_idempotente_y_se_pinta(self):
        call_command("crear_demo_fiesta", stdout=StringIO())
        call_command("crear_demo_fiesta", "--host", "192.168.1.50:8000", stdout=StringIO())

        self.assertEqual(Plantilla.objects.filter(slug_tema="fiesta-neon-01").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-fiesta")
        self.assertEqual(invitacion.plantilla.color_tema, "#0E0A1A")
        self.assertTrue(invitacion.musica_url.startswith("http://192.168.1.50:8000/"))
        self.assertNotIn("itinerario", invitacion.contenido_extra)

        respuesta = self.client.get("/invitaciones/demo-fiesta/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Cumpleaños #30")
        self.assertContains(respuesta, "/static/invitaciones/pwa/fiesta-neon-01-180.png")


class DemoXVTests(TestCase):
    def test_crear_demo_xv_usa_la_hora_local(self):
        call_command("crear_demo_xv", stdout=StringIO())
        invitacion = Invitacion.objects.get(slug="demo-xv-valentina")
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 19)


class DemoBabyShowerTests(TestCase):
    def test_crear_demo_baby_shower_es_idempotente_y_se_pinta(self):
        call_command("crear_demo_baby_shower", stdout=StringIO())
        call_command("crear_demo_baby_shower", stdout=StringIO())
        self.assertEqual(Invitacion.objects.filter(slug="baby-shower-demo").count(), 1)

        invitacion = Invitacion.objects.get(slug="baby-shower-demo")
        self.assertTrue(invitacion.plantilla.soporta_votacion)
        # la hora del demo es 5:00 PM en hora de México
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 17)

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        for fragmento in ('id="dulce-espera"', 'id="votacion"', 'id="regalos"', 'id="panales"'):
            self.assertContains(respuesta, fragmento)

    def test_service_worker_no_guarda_en_cache_la_votacion(self):
        # si el SW cacheara /votar/conteo/, el juego en vivo mostraría datos viejos
        respuesta = self.client.get(reverse("invitaciones:service_worker"))
        self.assertContains(respuesta, "'/votar/'")
