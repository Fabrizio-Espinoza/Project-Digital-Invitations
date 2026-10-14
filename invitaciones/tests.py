import json
from datetime import datetime, timedelta
from io import StringIO
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import Client, TestCase, override_settings
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
        invitacion = Invitacion.objects.get(slug="demo-fiesta-sofia")
        self.assertEqual(invitacion.plantilla.color_tema, "#0E0A1A")
        self.assertTrue(invitacion.musica_url.startswith("http://192.168.1.50:8000/"))
        self.assertNotIn("itinerario", invitacion.contenido_extra)

        respuesta = self.client.get("/invitaciones/demo-fiesta-sofia/")
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
        self.assertEqual(Invitacion.objects.filter(slug="demo-baby-mariana-diego").count(), 1)

        invitacion = Invitacion.objects.get(slug="demo-baby-mariana-diego")
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


class DemoCarnetDeBaileTests(TestCase):
    def test_crear_demo_xv_carnet_es_idempotente_y_se_pinta(self):
        call_command("crear_demo_xv_carnet", stdout=StringIO())
        # la IP se acepta con o sin "http://"
        call_command("crear_demo_xv_carnet", "--host", "http://192.168.1.50:8000", stdout=StringIO())

        self.assertEqual(Plantilla.objects.filter(slug_tema="xv-carnet-02").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-xv-regina")
        self.assertEqual(invitacion.plantilla.color_tema, "#F9DDE3")
        self.assertEqual(invitacion.musica_url, "http://192.168.1.50:8000/static/invitaciones/musica/cancion-boda.mp3")
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 18)

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/xv-carnet-02.html")
        # el regalo nace oculto: si el JS falla, nunca tapa la invitación
        self.assertContains(respuesta, 'id="regalo" hidden')
        self.assertContains(respuesta, "/static/invitaciones/pwa/xv-carnet-02-180.png")


class DemoTerracotaTests(TestCase):
    def test_crear_demo_terracota_es_idempotente_y_se_pinta(self):
        call_command("crear_demo_terracota", stdout=StringIO())
        call_command("crear_demo_terracota", "--host", "192.168.1.50:8000", stdout=StringIO())

        self.assertEqual(Plantilla.objects.filter(slug_tema="boda-minimal-01").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-boda-daniela-andres")
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 17)

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/boda-minimal-01.html")
        self.assertContains(respuesta, "Daniela &amp; Andrés")


class DemoCobaltoTests(TestCase):
    def test_crear_demo_cobalto_es_idempotente_y_se_pinta(self):
        call_command("crear_demo_cobalto", stdout=StringIO())
        call_command("crear_demo_cobalto", stdout=StringIO())

        self.assertEqual(Invitacion.objects.filter(slug="demo-cobalto-editorial").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-cobalto-editorial")
        self.assertEqual(invitacion.plantilla.color_tema, "#1F3FA3")

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/boda-editorial-02.html")
        self.assertContains(respuesta, "/static/invitaciones/pwa/boda-editorial-02-180.png")


class DemoTareaCumplidaTests(TestCase):
    def test_crear_demo_graduacion_cuaderno_es_idempotente_y_se_pinta(self):
        call_command("crear_demo_graduacion_cuaderno", stdout=StringIO())
        call_command("crear_demo_graduacion_cuaderno", "--host", "192.168.1.50:8000", stdout=StringIO())

        self.assertEqual(Plantilla.objects.filter(slug_tema="graduacion-cuaderno-02").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-graduacion-diego")
        self.assertEqual(invitacion.plantilla.tipo_evento, "graduacion")
        self.assertTrue(invitacion.musica_url.startswith("http://192.168.1.50:8000/"))
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 17)

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/graduacion-cuaderno-02.html")
        # los datos escolares (mismas claves que "Laurel de Oro") y la etiqueta propia de los padres
        self.assertContains(respuesta, "Ingeniería Mecatrónica")
        self.assertContains(respuesta, "Gracias a mis papás")
        self.assertContains(respuesta, "/static/invitaciones/pwa/graduacion-cuaderno-02-180.png")


class DemoLoteriaTests(TestCase):
    def test_crear_demo_loteria_es_idempotente_y_se_pinta(self):
        call_command("crear_demo_loteria", stdout=StringIO())
        call_command("crear_demo_loteria", "--host", "192.168.1.50:8000", stdout=StringIO())

        self.assertEqual(Plantilla.objects.filter(slug_tema="fiesta-loteria-02").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-loteria-lupita")
        self.assertEqual(invitacion.plantilla.tipo_evento, "fiesta")
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 14)

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/fiesta-loteria-02.html")
        # la carta del festejado sale de contenido_extra
        self.assertContains(respuesta, '<span class="carta-numero">80</span>', html=False)
        self.assertContains(respuesta, "La Cumpleañera")
        self.assertContains(respuesta, "/static/invitaciones/pwa/fiesta-loteria-02-180.png")

    def test_carta_de_pinata_cambia_el_dibujo(self):
        call_command("crear_demo_loteria", stdout=StringIO())
        invitacion = Invitacion.objects.get(slug="demo-loteria-lupita")
        invitacion.contenido_extra["carta_dibujo"] = "pinata"
        invitacion.save()
        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        # al frente va la piñata y el pastel pasa a una carta de atrás
        self.assertContains(respuesta, "El Pastel")


class DemoEntregaEspecialTests(TestCase):
    def test_crear_demo_baby_entrega_es_idempotente_y_se_pinta(self):
        call_command("crear_demo_baby_entrega", stdout=StringIO())
        call_command("crear_demo_baby_entrega", "--host", "192.168.1.50:8000", stdout=StringIO())

        self.assertEqual(Plantilla.objects.filter(slug_tema="baby-shower-entrega-02").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-baby-entrega")
        self.assertTrue(invitacion.plantilla.soporta_votacion)
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 17)

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/baby-shower-entrega-02.html")
        # todas las secciones de baby shower del motor, vestidas por este tema
        for fragmento in ('id="dulce-espera"', 'id="votacion"', 'id="regalos"', 'id="panales"',
                          'class="rastreo-estados"', "¿Qué trae el paquete?"):
            self.assertContains(respuesta, fragmento)
        # la guía de envío usa la fecha probable de parto como número de guía
        guia = "Guía BB-" + invitacion.contenido_extra["fecha_probable_parto"].replace("-", "")
        self.assertContains(respuesta, guia)
        self.assertContains(respuesta, "/static/invitaciones/pwa/baby-shower-entrega-02-180.png")


class DemoHotelAmorTests(TestCase):
    def test_crear_demo_hotel_es_idempotente_y_se_pinta(self):
        call_command("crear_demo_hotel", stdout=StringIO())
        call_command("crear_demo_hotel", "--host", "http://192.168.1.50:8000", stdout=StringIO())

        self.assertEqual(Plantilla.objects.filter(slug_tema="boda-hotel-03").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-hotel-amor")
        self.assertEqual(invitacion.musica_url, "http://192.168.1.50:8000/static/invitaciones/musica/cancion-boda.mp3")
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 18)

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/boda-hotel-03.html")
        # toldo, escudo con el año, check-in con la fecha en minúsculas y la llave del RSVP
        for fragmento in ('class="toldo"', "Est. 2027", "sábado 8 de mayo", "Su reservación",
                          'id="h-llave"', "rsvp:enviado", 'class="nota-ninos"'):
            self.assertContains(respuesta, fragmento)
        self.assertContains(respuesta, "/static/invitaciones/pwa/boda-hotel-03-180.png")


class DemoLaGiraTests(TestCase):
    def test_crear_demo_xv_gira_es_idempotente_y_se_pinta(self):
        call_command("crear_demo_xv_gira", stdout=StringIO())
        call_command("crear_demo_xv_gira", "--host", "192.168.1.50:8000", stdout=StringIO())

        self.assertEqual(Plantilla.objects.filter(slug_tema="xv-gira-03").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-xv-ximena")
        self.assertEqual(invitacion.plantilla.tipo_evento, "xv")
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 18)

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/xv-gira-03.html")
        # "Sáb" con acento (Django abrevia "Sab"), la ciudad del poster y la pulsera del RSVP
        for fragmento in ('class="marquesina"', "Sáb 12 Jun 2027", "Guadalajara, Jal.", "Tu boleto",
                          "rsvp:enviado", "family=Mrs+Saint+Delafield&text=Ximena"):
            self.assertContains(respuesta, fragmento)
        self.assertContains(respuesta, "/static/invitaciones/pwa/xv-gira-03-180.png")

    def test_no_pisa_el_demo_de_medianoche_dorada(self):
        call_command("crear_demo_xv", stdout=StringIO())
        call_command("crear_demo_xv_gira", stdout=StringIO())
        self.assertEqual(Invitacion.objects.get(slug="demo-xv-valentina").plantilla.slug_tema, "xv-medianoche-01")


class DemoProximaSalidaTests(TestCase):
    def test_crear_demo_graduacion_salida_es_idempotente_y_se_pinta(self):
        call_command("crear_demo_graduacion_salida", stdout=StringIO())
        call_command("crear_demo_graduacion_salida", "--host", "192.168.1.50:8000", stdout=StringIO())

        self.assertEqual(Plantilla.objects.filter(slug_tema="graduacion-salida-03").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-graduacion-camila")
        self.assertEqual(invitacion.plantilla.tipo_evento, "graduacion")
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 17)

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/graduacion-salida-03.html")
        # tablero con destino = carrera, "Sáb" con acento, pase ESC -> FUT y la fila del pasajero
        for fragmento in ('class="tablero-vuelo"', "Relaciones Internacionales", "Sáb 19 Jun",
                          "<strong>FUT</strong>", "rsvp:enviado", 'id="estatus-vuelo"'):
            self.assertContains(respuesta, fragmento)
        self.assertContains(respuesta, "/static/invitaciones/pwa/graduacion-salida-03-180.png")


class DemoNivelDesbloqueadoTests(TestCase):
    def test_crear_demo_fiesta_consola_es_idempotente_y_se_pinta(self):
        call_command("crear_demo_fiesta_consola", stdout=StringIO())
        call_command("crear_demo_fiesta_consola", "--host", "192.168.1.50:8000", stdout=StringIO())

        self.assertEqual(Plantilla.objects.filter(slug_tema="fiesta-consola-03").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-fiesta-rodrigo")
        self.assertEqual(invitacion.plantilla.tipo_evento, "fiesta")
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 20)

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/fiesta-consola-03.html")
        # "Nivel 30" sale de la clave nivel; controles de la consola; SELECT = agendar (.ics)
        for fragmento in ("Nivel 30 desbloqueado", 'id="boton-a"', 'id="boton-start"',
                          "Sáb 14 Nov", "rsvp:enviado", "Llega a la fiesta"):
            self.assertContains(respuesta, fragmento)
        self.assertContains(respuesta, 'class="boton-select" href="' + reverse("invitaciones:calendario", args=[invitacion.slug]))
        self.assertContains(respuesta, "/static/invitaciones/pwa/fiesta-consola-03-180.png")


class DemoPancitoEnElHornoTests(TestCase):
    def test_crear_demo_baby_pancito_es_idempotente_y_se_pinta(self):
        call_command("crear_demo_baby_pancito", stdout=StringIO())
        call_command("crear_demo_baby_pancito", "--host", "192.168.1.50:8000", stdout=StringIO())

        self.assertEqual(Plantilla.objects.filter(slug_tema="baby-shower-panaderia-03").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-baby-pancito")
        self.assertTrue(invitacion.plantilla.soporta_votacion)
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 17)

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/baby-shower-panaderia-03.html")
        # todas las secciones de baby shower del motor, vestidas de panadería
        for fragmento in ('id="dulce-espera"', 'id="votacion"', 'id="regalos"', 'id="panales"',
                          'id="c-concha"', "¿De qué sabor viene?", "Una tarde dulce", "rsvp:enviado"):
            self.assertContains(respuesta, fragmento)
        self.assertContains(respuesta, "/static/invitaciones/pwa/baby-shower-panaderia-03-180.png")


class MusicaYPruebaEnCelularTests(TestCase):
    def test_musica_de_static_no_depende_de_la_ip(self):
        invitacion = Invitacion(musica_url="http://192.168.100.18:8000/static/invitaciones/musica/cancion-boda.mp3")
        self.assertEqual(invitacion.musica_src, "/static/invitaciones/musica/cancion-boda.mp3")
        externa = Invitacion(musica_url="https://ejemplo.com/cancion.mp3")
        self.assertEqual(externa.musica_src, "https://ejemplo.com/cancion.mp3")
        self.assertEqual(Invitacion(musica_url="").musica_src, "")

    def test_el_audio_usa_la_ruta_relativa(self):
        call_command("crear_demo_hotel", "--host", "192.168.100.18:8000", stdout=StringIO())
        respuesta = self.client.get(reverse("invitaciones:detalle", args=["demo-hotel-amor"]))
        self.assertContains(respuesta, 'src="/static/invitaciones/musica/cancion-boda.mp3"')

    @override_settings(DEBUG=True, CSRF_TRUSTED_ORIGINS=["https://*.trycloudflare.com"])
    def test_rsvp_por_tunel_https_no_da_403(self):
        call_command("crear_demo_hotel", stdout=StringIO())
        cliente = Client(enforce_csrf_checks=True)
        dominio = "prueba-abc.trycloudflare.com"
        cliente.get(reverse("invitaciones:detalle", args=["demo-hotel-amor"]), HTTP_HOST=dominio)
        token = cliente.cookies["csrftoken"].value
        respuesta = cliente.post(
            reverse("invitaciones:rsvp", args=["demo-hotel-amor"]),
            data=json.dumps({"nombre_invitado": "Ana", "asistencia": "si", "num_acompanantes": 0}),
            content_type="application/json",
            HTTP_HOST=dominio, HTTP_ORIGIN=f"https://{dominio}", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(respuesta.status_code, 200)

    def test_crear_todos_los_demos(self):
        salida = StringIO()
        call_command("crear_todos_los_demos", "--host", "192.168.100.18:8000", stdout=salida)
        self.assertIn("http://192.168.100.18:8000/invitaciones/demo-baby-pancito/", salida.getvalue())
        self.assertEqual(Invitacion.objects.filter(slug__startswith="demo-").count(), 20)


# ---------------------------------------------------------------------------
# Producción: validación y límite del RSVP, privacidad, retención, respaldos
# ---------------------------------------------------------------------------
import gzip
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings as django_settings
from django.core.cache import cache

from .checks import revisar_aviso_privacidad, revisar_ruta_admin
from .management.commands.respaldar_bd import Command as ComandoRespaldo
from .models import Confirmacion


class BaseRsvpTests(TestCase):
    def setUp(self):
        cache.clear()
        call_command("crear_demo_hotel", stdout=StringIO())
        self.invitacion = Invitacion.objects.get(slug="demo-hotel-amor")
        self.url = reverse("invitaciones:rsvp", args=[self.invitacion.slug])

    def enviar(self, datos=None, cuerpo=None, **extra):
        cuerpo = cuerpo if cuerpo is not None else json.dumps(datos)
        return self.client.post(self.url, data=cuerpo, content_type="application/json", **extra)

    def valido(self, **cambios):
        datos = {"nombre_invitado": "Ana López", "asistencia": "si", "num_acompanantes": "1", "mensaje": ""}
        datos.update(cambios)
        return datos


class ValidacionRsvpTests(BaseRsvpTests):
    def test_respuesta_valida_se_guarda(self):
        respuesta = self.enviar(self.valido())
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["total_confirmados"], 1)
        self.assertEqual(Confirmacion.objects.get().num_acompanantes, 1)

    def test_datos_malos_dan_400_y_no_500(self):
        casos = [
            ({"asistencia": "si"}, "Escribe tu nombre."),
            (self.valido(nombre_invitado="   "), "Escribe tu nombre."),
            (self.valido(nombre_invitado="x" * 151), "El nombre es demasiado largo."),
            (self.valido(asistencia="quizas"), "Elige si vas a asistir."),
            (self.valido(num_acompanantes="abc"), "El número de acompañantes no es válido."),
            (self.valido(num_acompanantes=500), "El número de acompañantes debe estar entre 0 y 20."),
            (self.valido(num_acompanantes=-1), "El número de acompañantes debe estar entre 0 y 20."),
            (self.valido(mensaje="x" * 1001), "El mensaje es demasiado largo (máximo 1000 caracteres)."),
            (["no", "es", "objeto"], "Datos no válidos."),
        ]
        for datos, mensaje in casos:
            with self.subTest(datos=str(datos)[:60]):
                respuesta = self.enviar(datos)
                self.assertEqual(respuesta.status_code, 400)
                self.assertEqual(respuesta.json()["error"], mensaje)
        self.assertEqual(self.enviar(cuerpo="{esto no es json").status_code, 400)
        self.assertFalse(Confirmacion.objects.exists())

    def test_doble_toque_no_cuenta_doble(self):
        self.enviar(self.valido())
        respuesta = self.enviar(self.valido(nombre_invitado="ana lópez"))
        self.assertEqual(respuesta.json()["total_confirmados"], 1)
        self.assertEqual(Confirmacion.objects.count(), 1)
        # otra persona, u otra respuesta, sí cuenta
        self.enviar(self.valido(nombre_invitado="Luis"))
        self.enviar(self.valido(asistencia="no"))
        self.assertEqual(Confirmacion.objects.count(), 3)


class LimiteRsvpTests(BaseRsvpTests):
    @override_settings(LIMITES_RSVP={"por_ip": (2, 600), "por_invitacion": (100, 3600)})
    def test_por_ip(self):
        for i in range(2):
            self.assertEqual(self.enviar(self.valido(nombre_invitado=f"Invitado {i}")).status_code, 200)
        bloqueada = self.enviar(self.valido(nombre_invitado="Spam"))
        self.assertEqual(bloqueada.status_code, 429)
        self.assertIn("Espera unos minutos", bloqueada.json()["error"])
        self.assertEqual(bloqueada["Retry-After"], "600")
        # otra conexión sigue pudiendo confirmar
        otra = self.enviar(self.valido(nombre_invitado="Prima"), REMOTE_ADDR="10.0.0.99")
        self.assertEqual(otra.status_code, 200)
        self.assertEqual(Confirmacion.objects.count(), 3)

    @override_settings(LIMITES_RSVP={"por_ip": (100, 600), "por_invitacion": (3, 3600)})
    def test_tope_por_invitacion(self):
        for i in range(3):
            self.enviar(self.valido(nombre_invitado=f"Invitado {i}"), REMOTE_ADDR=f"10.0.0.{i}")
        self.assertEqual(self.enviar(self.valido(nombre_invitado="Uno más"), REMOTE_ADDR="10.0.0.50").status_code, 429)

    @override_settings(LIMITES_RSVP={"por_ip": (1, 600), "por_invitacion": (100, 3600)},
                       CABECERA_IP_CLIENTE="HTTP_X_REAL_IP")
    def test_detras_del_balanceador_usa_la_ip_real(self):
        # todos llegan desde la misma IP del balanceador, pero con distinta X-Real-IP
        for i in range(3):
            respuesta = self.enviar(self.valido(nombre_invitado=f"Invitado {i}"),
                                    REMOTE_ADDR="10.9.9.9", HTTP_X_REAL_IP=f"187.1.1.{i}")
            self.assertEqual(respuesta.status_code, 200)
        repetido = self.enviar(self.valido(nombre_invitado="Otra vez"),
                               REMOTE_ADDR="10.9.9.9", HTTP_X_REAL_IP="187.1.1.0")
        self.assertEqual(repetido.status_code, 429)

    @override_settings(LIMITES_VOTO={"por_ip": (2, 600), "por_invitacion": (100, 3600)})
    def test_votos_tambien_tienen_limite(self):
        call_command("crear_demo_baby_pancito", stdout=StringIO())
        url = reverse("invitaciones:votar", args=["demo-baby-pancito"])
        codigos = [
            self.client.post(url, data=json.dumps({"opcion": "nina"}), content_type="application/json").status_code
            for _ in range(3)
        ]
        self.assertEqual(codigos, [200, 200, 429])
        self.assertEqual(Voto.objects.count(), 2)


class PrivacidadTests(TestCase):
    def test_pagina_con_datos_faltantes_los_marca(self):
        respuesta = self.client.get(reverse("aviso_privacidad"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "[Nombre o razón social del responsable]")
        self.assertContains(respuesta, f"{django_settings.DIAS_RETENCION_DATOS} días después")

    @override_settings(AVISO_RESPONSABLE="Fabrizio Espinoza", AVISO_DOMICILIO="Calle 1, CDMX",
                       AVISO_CORREO="privacidad@ejemplo.mx", MARCA_NOMBRE="Marca")
    def test_pagina_con_datos(self):
        respuesta = self.client.get(reverse("aviso_privacidad"))
        self.assertContains(respuesta, "Fabrizio Espinoza")
        self.assertContains(respuesta, "mailto:privacidad@ejemplo.mx")
        self.assertNotContains(respuesta, 'class="falta"')
        self.assertEqual(revisar_aviso_privacidad(None), [])

    def test_cada_invitacion_enlaza_el_aviso(self):
        call_command("crear_demo_xv_gira", stdout=StringIO())
        respuesta = self.client.get(reverse("invitaciones:detalle", args=["demo-xv-ximena"]))
        self.assertContains(respuesta, 'class="aviso-privacidad"')
        self.assertContains(respuesta, 'href="/privacidad/"')

    def test_check_deploy_avisa_lo_pendiente(self):
        self.assertEqual(revisar_aviso_privacidad(None)[0].id, "invitaciones.W001")
        self.assertEqual(revisar_ruta_admin(None)[0].id, "invitaciones.W002")
        with override_settings(ADMIN_URL="panel-7k2q/"):
            self.assertEqual(revisar_ruta_admin(None), [])


class RetencionDatosTests(TestCase):
    def test_borra_solo_eventos_viejos(self):
        call_command("crear_demo_hotel", stdout=StringIO())
        call_command("crear_demo_baby_pancito", stdout=StringIO())
        vieja = Invitacion.objects.get(slug="demo-hotel-amor")
        vieja.fecha_evento = timezone.now() - timedelta(days=120)
        vieja.save()
        reciente = Invitacion.objects.get(slug="demo-baby-pancito")
        for inv in (vieja, reciente):
            Confirmacion.objects.create(invitacion=inv, nombre_invitado="Ana", asistencia="si")
            Voto.objects.create(invitacion=inv, opcion="nina")

        call_command("borrar_datos_vencidos", "--simular", stdout=StringIO())
        self.assertEqual(Confirmacion.objects.count(), 2)

        call_command("borrar_datos_vencidos", stdout=StringIO())
        self.assertEqual(list(Confirmacion.objects.values_list("invitacion__slug", flat=True)), ["demo-baby-pancito"])
        self.assertEqual(list(Voto.objects.values_list("invitacion__slug", flat=True)), ["demo-baby-pancito"])
        self.assertTrue(Invitacion.objects.filter(slug="demo-hotel-amor").exists())   # la invitación se queda


class RespaldoTests(TestCase):
    def test_copia_consistente_y_rotacion(self):
        with tempfile.TemporaryDirectory() as carpeta:
            carpeta = Path(carpeta)
            original = carpeta / "original.sqlite3"
            conexion = sqlite3.connect(original)
            conexion.execute("create table rsvp (nombre text)")
            conexion.execute("insert into rsvp values ('Ana'), ('Luis')")
            conexion.commit()
            conexion.close()

            comando = ComandoRespaldo(stdout=StringIO())
            for sello in ("2026-01-01", "2026-01-02", "2026-01-03"):
                comando._respaldar_sqlite(original, carpeta / f"bd-{sello}.sqlite3.gz")
            comando._rotar(carpeta, "bd-", 2)
            respaldos = sorted(p.name for p in carpeta.glob("bd-*"))
            self.assertEqual(respaldos, ["bd-2026-01-02.sqlite3.gz", "bd-2026-01-03.sqlite3.gz"])

            restaurada = carpeta / "restaurada.sqlite3"
            restaurada.write_bytes(gzip.decompress((carpeta / respaldos[-1]).read_bytes()))
            conexion = sqlite3.connect(restaurada)
            self.assertEqual(conexion.execute("select count(*) from rsvp").fetchone()[0], 2)
            conexion.close()


class PaginasDeErrorTests(TestCase):
    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_404_amable_sin_detalles_tecnicos(self):
        respuesta = self.client.get("/invitaciones/no-existe/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertContains(respuesta, "Esta invitación no está disponible", status_code=404)
        self.assertNotContains(respuesta, "Traceback", status_code=404)


class SettingsProduccionTests(TestCase):
    """Se importan en un proceso aparte para no mezclar con los settings de prueba."""

    def correr(self, codigo, **entorno):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "AVISO_", "MARCA_"))}
        env["DJANGO_ARCHIVO_ENV"] = "/no/existe/.env"   # que no lea un .env real de la compu
        env.update(entorno)
        return subprocess.run([sys.executable, "-c", codigo], cwd=django_settings.BASE_DIR,
                              env=env, capture_output=True, text=True)

    def test_produccion_segura(self):
        resultado = self.correr(
            "from invitaciones_core import settings_produccion as s;"
            "print(s.DEBUG, s.SECRET_KEY, s.ALLOWED_HOSTS, s.CSRF_TRUSTED_ORIGINS, s.ADMIN_URL,"
            " s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE, 'whitenoise.middleware.WhiteNoiseMiddleware' in s.MIDDLEWARE)",
            DJANGO_SECRET_KEY="llave-de-prueba", DJANGO_ALLOWED_HOSTS="www.ejemplo.mx, .ejemplo.mx",
            DJANGO_ADMIN_URL="/panel-x/",
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(resultado.stdout.strip(),
                         "False llave-de-prueba ['www.ejemplo.mx', '.ejemplo.mx'] "
                         "['https://www.ejemplo.mx', 'https://*.ejemplo.mx'] panel-x/ True True True")

    def test_sin_secret_key_no_arranca(self):
        resultado = self.correr("from invitaciones_core import settings_produccion",
                                DJANGO_ALLOWED_HOSTS="www.ejemplo.mx")
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("Falta la variable DJANGO_SECRET_KEY", resultado.stderr)


class RenombreDemosViejosTests(TestCase):
    def test_los_demos_viejos_se_renombran_sin_duplicarse(self):
        viejos = {"crear_demo_fiesta": ("demo-fiesta", "demo-fiesta-sofia"),
                  "crear_demo_graduacion": ("demo-graduacion", "demo-graduacion-valeria-montes"),
                  "crear_demo_baby_shower": ("baby-shower-demo", "demo-baby-mariana-diego")}
        for comando, (viejo, nuevo) in viejos.items():
            with self.subTest(comando=comando):
                call_command(comando, stdout=StringIO())
                invitacion = Invitacion.objects.get(slug=nuevo)
                invitacion.slug = viejo          # como quedó en las bases de antes
                invitacion.save()
                Confirmacion.objects.create(invitacion=invitacion, nombre_invitado="Ana", asistencia="si")

                call_command(comando, stdout=StringIO())
                self.assertFalse(Invitacion.objects.filter(slug=viejo).exists())
                renombrada = Invitacion.objects.get(slug=nuevo)
                self.assertEqual(renombrada.pk, invitacion.pk)       # la misma, no una nueva
                self.assertEqual(renombrada.confirmaciones.count(), 1)


# ---------------------------------------------------------------------------
# Catálogo (página principal)
# ---------------------------------------------------------------------------
from urllib.parse import unquote

from django.contrib.staticfiles import finders
from django.template.loader import get_template

from .catalogo import DISENOS, TIPOS, captura
from .checks import revisar_whatsapp
from .management.commands.crear_todos_los_demos import DEMOS


class CatalogoTests(TestCase):
    def test_cada_diseno_tiene_demo_plantilla_y_captura(self):
        # plantilla nueva sin agregar al catálogo (o al revés) = esta prueba falla
        self.assertEqual({d["demo"] for d in DISENOS}, {slug for _, slug, _ in DEMOS})
        self.assertEqual(len({d["slug_tema"] for d in DISENOS}), len(DISENOS))
        tipos = {clave for clave, _, _ in TIPOS}
        for diseno in DISENOS:
            with self.subTest(diseno=diseno["nombre"]):
                self.assertIn(diseno["tipo"], tipos)
                get_template(f"invitaciones/temas/{diseno['slug_tema']}.html")
                self.assertIsNotNone(finders.find(captura(diseno)), "falta correr capturar_catalogo")
        self.assertIsNotNone(finders.find("invitaciones/catalogo/compartir.jpg"))

    @override_settings(WHATSAPP_NUMERO="+52 55 1234-5678", MARCA_NOMBRE="InvitaVibra")
    def test_la_portada_muestra_los_disenos_y_el_whatsapp(self):
        call_command("crear_demo_xv_gira", stdout=StringIO())
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/catalogo.html")
        for diseno in DISENOS:
            self.assertContains(respuesta, diseno["nombre"])
        # el número se limpia y el mensaje dice qué diseño y qué evento
        html = unquote(respuesta.content.decode())
        self.assertIn("https://wa.me/525512345678?text=", html)
        self.assertIn("«La Gira» para unos XV años", html)
        # demo creado → link; demo que no existe en esta base → sin link (no a un 404)
        self.assertContains(respuesta, 'href="/invitaciones/demo-xv-ximena/"')
        self.assertNotContains(respuesta, 'href="/invitaciones/demo-hotel-amor/"')
        # la foto que sale al pegar el link en WhatsApp: URL absoluta y, fuera de DEBUG, siempre https
        self.assertContains(respuesta, 'property="og:image" content="https://testserver/static/invitaciones/catalogo/compartir.jpg"')

    def test_aviso_si_falta_el_whatsapp(self):
        with override_settings(WHATSAPP_NUMERO=""):
            self.assertEqual([a.id for a in revisar_whatsapp(None)], ["invitaciones.W003"])
        with override_settings(WHATSAPP_NUMERO="525512345678"):
            self.assertEqual(revisar_whatsapp(None), [])

    @override_settings(DEBUG=True)
    def test_en_desarrollo_la_imagen_para_compartir_respeta_http(self):
        # por WiFi (http://<ip>:8000) no hay https: forzarlo rompería la vista previa
        respuesta = self.client.get("/")
        self.assertContains(respuesta, 'content="http://testserver/static/invitaciones/catalogo/compartir.jpg"')


# ---------------------------------------------------------------------------
# Pedido: formulario del cliente
# ---------------------------------------------------------------------------
import shutil
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from .models import ImagenGaleria, Pedido
from .fotos import LADO_MAXIMO_FOTO

MEDIA_PRUEBAS = tempfile.mkdtemp(prefix="media-pruebas-")


def foto_de_prueba(nombre="foto.jpg", ancho=3000, alto=2000, con_gps=True):
    imagen = Image.new("RGB", (ancho, alto), (200, 120, 90))
    exif = Image.Exif()
    if con_gps:
        exif[0x8825] = {2: (19.0, 26.0, 0.0)}      # GPSInfo: latitud de la casa
    salida = BytesIO()
    imagen.save(salida, "JPEG", exif=exif)
    return SimpleUploadedFile(nombre, salida.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class PedidoTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_PRUEBAS, ignore_errors=True)

    def setUp(self):
        self.boda = Plantilla.objects.create(nombre="Hotel Amor", tipo_evento="boda", slug_tema="boda-hotel-03")
        self.pedido = Pedido.objects.create(cliente="Sofía (WhatsApp)", plantilla=self.boda, nivel="premium")
        self.url = reverse("pedido", args=[self.pedido.token])

    def datos_boda(self, **cambios):
        datos = {
            "anfitriones": "Sofía & Emiliano",
            "fecha": "2027-05-08",
            "hora": "18:00",
            "mensaje": "Ven a celebrar con nosotros.",
            "ceremonia_etiqueta": "Misa",
            "ceremonia_nombre": "Capilla de la hacienda",
            "ceremonia_mapa": "maps.app.goo.gl/abc",
            "recepcion_nombre": "Patio de los flamboyanes",
            "dresscode": "Formal de verano",
            "usar_color": "on",
            "color": "#1F4D3A",
            "admite_ninos": "no",
            "itinerario-hora": ["6:00 PM", "", "8:30 PM"],
            "itinerario-evento": ["Ceremonia", "", "Cena"],
            "padrinos-rol": ["Padres de la novia"],
            "padrinos-nombres": ["Laura & Jorge"],
            "mesa_regalos_url": "https://mesaderegalos.liverpool.com.mx/",
            "cancion": "Perfect – Ed Sheeran",
            "notas": "Que diga «Nos casamos»",
        }
        datos.update(cambios)
        return datos

    def test_el_token_es_largo_y_la_pagina_pide_lo_de_una_boda(self):
        self.assertGreaterEqual(len(self.pedido.token), 12)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["X-Robots-Tag"], "noindex, nofollow")
        for texto in ("Nombres de los novios", "Lugar de la ceremonia", "Programa del evento",
                      "Papás y padrinos", "Tu canción", "Elegir fotos"):
            self.assertContains(respuesta, texto)
        self.assertNotContains(respuesta, "Fecha probable de parto")
        self.assertEqual(self.client.get("/pedido/no-existe/").status_code, 404)

    def test_enviar_crea_la_invitacion_como_borrador(self):
        respuesta = self.client.post(self.url, self.datos_boda(fotos=[foto_de_prueba()]))
        self.assertRedirects(respuesta, f"{self.url}?listo=1")
        self.pedido.refresh_from_db()
        inv = self.pedido.invitacion
        self.assertFalse(inv.activa)
        self.assertEqual(inv.titulo_evento, "Boda de Sofía & Emiliano")
        self.assertEqual(timezone.localtime(inv.fecha_evento).hour, 18)
        extra = inv.contenido_extra
        self.assertEqual(extra["lugar_ceremonia_etiqueta"], "Misa")
        self.assertEqual(extra["lugar_ceremonia_mapa_url"], "https://maps.app.goo.gl/abc")
        self.assertEqual(extra["dresscode_color"], "#1F4D3A")
        self.assertIs(extra["admite_ninos"], False)
        # el renglón vacío del programa se ignora
        self.assertEqual(extra["itinerario"], [{"hora": "6:00 PM", "evento": "Ceremonia"}, {"hora": "8:30 PM", "evento": "Cena"}])
        self.assertEqual(extra["padrinos"], [{"rol": "Padres de la novia", "nombres": "Laura & Jorge"}])
        self.assertNotIn("lugar_direccion", extra)
        self.assertEqual(self.pedido.cancion, "Perfect – Ed Sheeran")

        # la foto se achica, se guarda en JPEG y pierde los datos EXIF (GPS)
        foto = inv.galeria.get()
        with Image.open(foto.imagen.path) as guardada:
            self.assertEqual(max(guardada.size), LADO_MAXIMO_FOTO)
            self.assertNotIn(0x8825, guardada.getexif())

        # borrador: la vista pública no la enseña, la vista previa sí
        self.assertEqual(self.client.get(reverse("invitaciones:detalle", args=[inv.slug])).status_code, 404)
        previa = self.client.get(reverse("pedido_vista_previa", args=[self.pedido.token]))
        self.assertEqual(previa.status_code, 200)
        self.assertContains(previa, "Vista previa")
        self.assertContains(previa, "Patio de los flamboyanes")
        self.assertContains(self.client.get(f"{self.url}?listo=1"), "Recibimos tus datos")

    def test_corregir_actualiza_la_misma_invitacion_sin_perder_lo_que_no_controla(self):
        self.client.post(self.url, self.datos_boda())
        inv = Pedido.objects.get(pk=self.pedido.pk).invitacion
        inv.contenido_extra["frase_superior"] = "¡Nos vamos de viaje!"     # algo que puso el dueño en el admin
        inv.save()

        # al volver a abrir el link, el cliente ve lo que ya mandó
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'value="Sofía &amp; Emiliano"')
        self.assertContains(respuesta, 'value="Laura &amp; Jorge"')

        self.client.post(self.url, self.datos_boda(dresscode="", usar_color="", **{"padrinos-rol": [], "padrinos-nombres": []}))
        self.assertEqual(Invitacion.objects.count(), 1)
        inv.refresh_from_db()
        self.assertNotIn("dresscode", inv.contenido_extra)
        self.assertNotIn("dresscode_color", inv.contenido_extra)
        self.assertNotIn("padrinos", inv.contenido_extra)
        self.assertEqual(inv.contenido_extra["frase_superior"], "¡Nos vamos de viaje!")

    def test_errores_se_explican_y_no_se_crea_nada(self):
        datos = self.datos_boda(anfitriones="", ceremonia_nombre="", recepcion_nombre="",
                                **{"itinerario-hora": ["7:00 PM"], "itinerario-evento": [""]})
        respuesta = self.client.post(self.url, datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Revisa lo que está en rojo")
        self.assertContains(respuesta, "Escribe al menos un lugar")
        self.assertContains(respuesta, "le falta «¿Qué pasa?»")
        self.assertFalse(Invitacion.objects.exists())

    def test_foto_que_no_es_imagen_se_rechaza(self):
        falsa = SimpleUploadedFile("virus.jpg", b"no soy una foto", content_type="image/jpeg")
        respuesta = self.client.post(self.url, self.datos_boda(fotos=[falsa]))
        self.assertContains(respuesta, "no se pudo abrir")
        self.assertFalse(ImagenGaleria.objects.exists())

    def test_publicada_ya_no_se_edita(self):
        self.client.post(self.url, self.datos_boda())
        inv = Pedido.objects.get(pk=self.pedido.pk).invitacion
        inv.activa = True
        inv.save()
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, "ya está publicada")
        self.client.post(self.url, self.datos_boda(anfitriones="Otro nombre"))
        inv.refresh_from_db()
        self.assertEqual(inv.anfitriones, "Sofía & Emiliano")

    def test_baby_shower_pide_lo_suyo_y_arma_votacion_y_panales(self):
        baby = Plantilla.objects.create(nombre="Pancito", tipo_evento="baby_shower",
                                        slug_tema="baby-shower-panaderia-03", soporta_votacion=True)
        pedido = Pedido.objects.create(cliente="Mariana", plantilla=baby, nivel="premium")
        url = reverse("pedido", args=[pedido.token])
        self.assertContains(self.client.get(url), "Fecha probable de parto")
        self.client.post(url, {
            "anfitriones": "Mariana & Diego", "fecha": "2027-01-10", "hora": "17:00",
            "lugar_nombre": "Casa de la abuela", "lugar_direccion": "Coyoacán",
            "fecha_probable_parto": "2027-02-06", "votacion": "on", "lluvia_panales": "on",
            "mesas_regalos-nombre": ["Liverpool"], "mesas_regalos-codigo": ["51384920"],
            "mesas_regalos-url": ["mesaderegalos.liverpool.com.mx"],
        })
        pedido.refresh_from_db()
        extra = pedido.invitacion.contenido_extra
        self.assertEqual(pedido.invitacion.lugar_nombre, "Casa de la abuela")
        self.assertEqual(extra["fecha_probable_parto"], "2027-02-06")
        self.assertEqual([o["clave"] for o in extra["votacion"]["opciones"]], ["nina", "nino"])
        self.assertEqual(len(extra["lluvia_panales"]), 4)
        self.assertEqual(extra["mesas_regalos"][0]["url"], "https://mesaderegalos.liverpool.com.mx")

    def test_admin_muestra_el_link_y_publica(self):
        admin = User.objects.create_superuser("dueno", "d@ejemplo.mx", "clave-larga-123")
        self.client.force_login(admin)
        cambio = self.client.get(reverse("admin:invitaciones_pedido_change", args=[self.pedido.pk]))
        self.assertContains(cambio, self.url)
        self.assertContains(cambio, "Copiar mensaje para WhatsApp")

        self.client.post(self.url, self.datos_boda())
        self.client.post(reverse("admin:invitaciones_pedido_changelist"),
                         {"action": "publicar", "_selected_action": [self.pedido.pk]})
        self.pedido.refresh_from_db()
        self.assertTrue(self.pedido.invitacion.activa)
        self.assertEqual(self.client.get(reverse("invitaciones:detalle", args=[self.pedido.invitacion.slug])).status_code, 200)


@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class PedidoValoresPorDefectoTests(TestCase):
    def pedido(self, slug_tema, tipo):
        plantilla = Plantilla.objects.create(nombre=slug_tema, tipo_evento=tipo, slug_tema=slug_tema)
        return Pedido.objects.create(cliente="Ana", plantilla=plantilla, nivel="premium")

    def test_lo_minimo_se_completa_sin_inventar(self):
        pedido = self.pedido("boda-hotel-03", "boda")
        self.client.post(reverse("pedido", args=[pedido.token]), {
            "anfitriones": "Ana & Luis", "fecha": "2027-05-08", "hora": "18:00",
            "recepcion_nombre": "Jardín Los Arcos",
        })
        inv = Pedido.objects.get(pk=pedido.pk).invitacion
        self.assertIn("unimos nuestras vidas", inv.mensaje_bienvenida)
        self.assertEqual(inv.contenido_extra["lugar_recepcion_mapa_url"],
                         "https://www.google.com/maps/search/?api=1&query=Jard%C3%ADn%20Los%20Arcos")
        # lo que sería inventar se queda fuera: la plantilla esconde esa parte
        for clave in ("dresscode", "itinerario", "admite_ninos", "mesa_regalos_url", "lugar_ceremonia_mapa_url"):
            self.assertNotIn(clave, inv.contenido_extra)
        # el mensaje que sí escriben se respeta
        self.client.post(reverse("pedido", args=[pedido.token]), {
            "anfitriones": "Ana & Luis", "fecha": "2027-05-08", "hora": "18:00",
            "recepcion_nombre": "Jardín Los Arcos", "mensaje": "¡Nos casamos!",
        })
        inv.refresh_from_db()
        self.assertEqual(inv.mensaje_bienvenida, "¡Nos casamos!")

    def test_graduacion_con_un_solo_lugar(self):
        pedido = self.pedido("graduacion-salida-03", "graduacion")
        self.client.post(reverse("pedido", args=[pedido.token]), {
            "anfitriones": "Camila", "fecha": "2027-06-19", "hora": "17:00",
            "lugar_nombre": "Salón Aurora", "lugar_direccion": "Monterrey, N.L.",
        })
        inv = Pedido.objects.get(pk=pedido.pk).invitacion
        self.assertEqual(inv.contenido_extra["generacion"], "2027")
        self.assertIn("query=Sal%C3%B3n%20Aurora%2C%20Monterrey%2C%20N.L.", inv.lugar_mapa_url)



@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class VistaPreviaProtegidaTests(TestCase):
    def test_la_vista_previa_lleva_marca_de_agua_y_desaparece_al_publicar(self):
        plantilla = Plantilla.objects.create(nombre="Hotel Amor", tipo_evento="boda", slug_tema="boda-hotel-03")
        pedido = Pedido.objects.create(cliente="Ana", plantilla=plantilla, nivel="premium")
        self.client.post(reverse("pedido", args=[pedido.token]), {
            "anfitriones": "Ana & Luis", "fecha": "2027-05-08", "hora": "18:00", "recepcion_nombre": "Jardín",
        })
        previa = reverse("pedido_vista_previa", args=[pedido.token])
        respuesta = self.client.get(previa)
        self.assertContains(respuesta, 'class="marca-agua"')
        # el RSVP de un borrador no recibe confirmaciones
        inv = Pedido.objects.get(pk=pedido.pk).invitacion
        self.assertEqual(self.client.post(reverse("invitaciones:rsvp", args=[inv.slug]),
                                          {"nombre": "X", "asistencia": "si"}).status_code, 404)

        inv.activa = True
        inv.save()
        self.assertRedirects(self.client.get(previa), reverse("invitaciones:detalle", args=[inv.slug]))
        self.assertNotContains(self.client.get(reverse("invitaciones:detalle", args=[inv.slug])), 'class="marca-agua"')


# ---------------------------------------------------------------------------
# Panel del anfitrión
# ---------------------------------------------------------------------------
class PanelAnfitrionTests(TestCase):
    def setUp(self):
        call_command("crear_demo_baby_shower", stdout=StringIO())
        self.inv = Invitacion.objects.get(slug="demo-baby-mariana-diego")
        for nombre, asistencia, acompanantes, mensaje in [
            ("Lucía Pérez", "si", 2, "¡Muchas felicidades!"),
            ("Tío Beto", "si", 0, ""),
            ("Karla", "tal_vez", 1, ""),
            ("Jorge", "no", 0, "Lo siento, estaré de viaje"),
        ]:
            Confirmacion.objects.create(invitacion=self.inv, nombre_invitado=nombre, asistencia=asistencia,
                                        num_acompanantes=acompanantes, mensaje=mensaje)
        Voto.objects.create(invitacion=self.inv, opcion="nina")
        self.url = reverse("panel_anfitrion", args=[self.inv.token_panel])

    def test_cada_invitacion_tiene_su_link_privado(self):
        otra = Invitacion.objects.create(plantilla=self.inv.plantilla, titulo_evento="Otra", anfitriones="X",
                                         fecha_evento=timezone.now())
        self.assertGreaterEqual(len(self.inv.token_panel), 12)
        self.assertNotEqual(self.inv.token_panel, otra.token_panel)
        self.assertNotEqual(self.inv.token_panel, self.inv.slug)
        self.assertEqual(self.client.get("/panel/no-existe/").status_code, 404)

    def test_el_panel_cuenta_personas_y_muestra_respuestas(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["X-Robots-Tag"], "noindex, nofollow")
        # personas = los que dicen que sí + sus acompañantes (1+2 y 1+0)
        self.assertEqual(respuesta.context["personas_si"], 4)
        self.assertEqual((respuesta.context["total_tal_vez"], respuesta.context["total_no"]), (1, 1))
        for texto in ("Lucía Pérez", "+2 acompañantes", "Estaré de viaje".lower()[1:], "Descargar lista"):
            self.assertContains(respuesta, texto)
        self.assertContains(respuesta, "Revelar: ¡Es niña!")
        self.assertIn("https://wa.me/?text=", respuesta.context["compartir_whatsapp"])
        self.assertContains(respuesta, "<span>personas confirmadas</span>", html=True)

    def test_con_una_sola_persona_el_panel_habla_en_singular(self):
        Confirmacion.objects.filter(invitacion=self.inv).exclude(nombre_invitado="Tío Beto").delete()
        self.assertContains(self.client.get(self.url), "<span>persona confirmada</span>", html=True)

    def test_la_lista_se_descarga_para_excel(self):
        respuesta = self.client.get(reverse("panel_lista_csv", args=[self.inv.token_panel]))
        contenido = respuesta.content.decode("utf-8")
        self.assertTrue(contenido.startswith("﻿"))     # BOM: Excel respeta los acentos
        self.assertIn("attachment", respuesta["Content-Disposition"])
        filas = contenido.lstrip("﻿").splitlines()
        self.assertEqual(filas[0], "Nombre,Respuesta,Acompañantes,Personas en total,Mensaje,Fecha de respuesta")
        self.assertEqual(len(filas), 5)
        self.assertIn("Lucía Pérez,Sí asistiré,2,3,¡Muchas felicidades!", contenido)
        self.assertIn("Jorge,No podré asistir,0,0", contenido)

    def test_revelar_el_resultado_desde_el_panel(self):
        revelar = reverse("panel_revelar", args=[self.inv.token_panel])
        self.assertEqual(self.client.get(revelar).status_code, 405)
        self.assertEqual(self.client.post(revelar, {"opcion": "inventada"}).status_code, 400)
        self.assertRedirects(self.client.post(revelar, {"opcion": "nino"}), self.url)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.contenido_extra["votacion"]["resultado"], "nino")
        # los invitados lo ven en el siguiente sondeo
        conteo = self.client.get(reverse("invitaciones:conteo_votos", args=[self.inv.slug])).json()
        self.assertEqual(conteo["resultado"], "nino")
        panel = self.client.get(self.url)
        self.assertNotContains(panel, 'name="opcion"')      # ya no hay botones de revelar
        self.assertContains(panel, "¡Es niño!")



class CargaLigeraTests(TestCase):
    def test_fotos_y_musica_no_se_descargan_al_abrir(self):
        call_command("crear_demo_hotel", stdout=StringIO())
        inv = Invitacion.objects.get(slug="demo-hotel-amor")
        ImagenGaleria.objects.create(invitacion=inv, imagen="invitaciones/galeria/x.jpg")
        respuesta = self.client.get(reverse("invitaciones:detalle", args=[inv.slug]))
        # la galería está pantallas más abajo: cada foto se baja al acercarse
        self.assertContains(respuesta, 'src="/media/invitaciones/galeria/x.jpg" alt="" loading="lazy" decoding="async"')
        # la canción pesa varios MB: solo se baja al tocar play
        self.assertContains(respuesta, 'preload="none"')


# ---------------------------------------------------------------------------
# Canción subida desde el admin
# ---------------------------------------------------------------------------
from django.core.exceptions import ValidationError as ErrorDeValidacion

from .models import validar_cancion

MP3_FALSO = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 2000      # cabecera ID3 de un MP3
M4A_FALSO = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 2000             # cabecera de un M4A


def datos_del_admin(pagina, inv):
    """Lo que manda el formulario de la invitación en el admin tal como está (sin archivos)."""
    datos = {campo.html_name: campo.value() for campo in pagina.context["adminform"].form
             if campo.value() is not None and campo.name not in Invitacion.ARCHIVOS_PROPIOS}
    datos["contenido_extra"] = json.dumps(inv.contenido_extra)
    datos["fecha_evento_0"], datos["fecha_evento_1"] = (
        timezone.localtime(inv.fecha_evento).strftime("%Y-%m-%d"),
        timezone.localtime(inv.fecha_evento).strftime("%H:%M:%S"))
    for prefijo in ("galeria", "confirmaciones"):
        datos.update({f"{prefijo}-TOTAL_FORMS": "0", f"{prefijo}-INITIAL_FORMS": "0"})
    return datos


@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class CancionSubidaTests(TestCase):
    def setUp(self):
        call_command("crear_demo_hotel", stdout=StringIO())
        self.inv = Invitacion.objects.get(slug="demo-hotel-amor")

    def test_solo_acepta_audio_de_verdad(self):
        validar_cancion(SimpleUploadedFile("a.mp3", MP3_FALSO))
        validar_cancion(SimpleUploadedFile("a.m4a", M4A_FALSO))
        with self.assertRaisesMessage(ErrorDeValidacion, "no parece una canción"):
            validar_cancion(SimpleUploadedFile("virus.mp3", b"<html>no soy musica</html>"))
        enorme = SimpleUploadedFile("larga.mp3", b"ID3" + b"\x00" * (15 * 1024 * 1024 + 1))
        with self.assertRaisesMessage(ErrorDeValidacion, "pesa más de 15 MB"):
            validar_cancion(enorme)

    def test_el_archivo_manda_sobre_el_link_y_suena_en_la_invitacion(self):
        self.inv.musica_url = ""
        self.inv.musica_archivo = SimpleUploadedFile("Perfect - Ed Sheeran.mp3", MP3_FALSO)
        self.inv.save()
        # nombre al azar en minúsculas, sin el nombre original
        self.assertRegex(self.inv.musica_archivo.name, r"^invitaciones/musica/[0-9a-f]{12}\.mp3$")
        self.assertEqual(self.inv.musica_src, f"/media/{self.inv.musica_archivo.name}")
        respuesta = self.client.get(reverse("invitaciones:detalle", args=[self.inv.slug]))
        self.assertContains(respuesta, f'preload="none" src="/media/{self.inv.musica_archivo.name}"')
        self.assertContains(respuesta, 'id="musica-fondo"')

    def test_cambiar_o_quitar_la_cancion_borra_el_archivo_viejo(self):
        self.inv.musica_archivo = SimpleUploadedFile("a.mp3", MP3_FALSO)
        self.inv.save()
        primera = Path(self.inv.musica_archivo.path)
        self.inv.musica_archivo = SimpleUploadedFile("b.mp3", MP3_FALSO)
        self.inv.save()
        segunda = Path(self.inv.musica_archivo.path)
        self.assertFalse(primera.exists())
        self.assertTrue(segunda.exists())
        self.inv.activa = False
        self.inv.save(update_fields=["activa"])        # guardar otra cosa no toca la canción
        self.assertTrue(segunda.exists())
        self.inv.musica_archivo = ""
        self.inv.save()
        self.assertFalse(segunda.exists())

    def test_el_admin_sube_la_cancion_y_muestra_lo_que_pidio_el_cliente(self):
        admin = User.objects.create_superuser("dueno", "d@ejemplo.mx", "clave-larga-123")
        self.client.force_login(admin)
        Pedido.objects.create(cliente="Sofía", plantilla=self.inv.plantilla, invitacion=self.inv,
                              cancion="Perfect – Ed Sheeran")
        url = reverse("admin:invitaciones_invitacion_change", args=[self.inv.pk])
        pagina = self.client.get(url)
        self.assertContains(pagina, "Perfect – Ed Sheeran")
        self.assertContains(pagina, 'name="musica_archivo"')

        # subir desde el formulario del admin: todos los campos + el archivo
        datos = datos_del_admin(pagina, self.inv)
        datos["musica_archivo"] = SimpleUploadedFile("cancion.mp3", MP3_FALSO)
        respuesta = self.client.post(url, datos)
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, "context", None)
                         and respuesta.context["adminform"].form.errors)
        self.inv.refresh_from_db()
        self.assertTrue(self.inv.musica_archivo.name.endswith(".mp3"))
        self.assertContains(self.client.get(url), "<audio controls")


# ---------------------------------------------------------------------------
# El Velo: la boda con foto de los novios en la portada
# ---------------------------------------------------------------------------
from .fotos import LADO_MAXIMO_PORTADA


@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class DemoElVeloTests(TestCase):
    def test_crear_demo_es_idempotente_y_la_portada_es_la_foto_bajo_el_velo(self):
        call_command("crear_demo_boda_velo", stdout=StringIO())
        carpeta = Path(Invitacion.objects.get(slug="demo-boda-renata-tomas").foto_portada.path).parent
        fotos_antes = set(os.listdir(carpeta))
        call_command("crear_demo_boda_velo", "--host", "http://192.168.1.50:8000", stdout=StringIO())

        self.assertEqual(Plantilla.objects.filter(slug_tema="boda-velo-04").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-boda-renata-tomas")
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 17)
        # la foto se copió una sola vez (la segunda corrida no la duplica)
        self.assertRegex(invitacion.foto_portada.name, r"^invitaciones/portadas/[0-9a-f]{12}\.jpg$")
        self.assertEqual(set(os.listdir(carpeta)), fotos_antes)

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/boda-velo-04.html")
        src = invitacion.foto_portada.url
        # la foto (con los nombres de alt), el velo que nace oculto, la foto del fondo y el recuerdo
        for fragmento in (f'class="portada-foto" src="{src}" alt="Renata &amp; Tomás"', 'id="velo" hidden',
                          "Levantar el velo", f'--foto-fondo: url("{src}")', 'id="plantilla-recuerdo"',
                          "rsvp:enviado", "Padrinos de velación", "El gran día"):
            self.assertContains(respuesta, fragmento)
        self.assertContains(respuesta, "/static/invitaciones/pwa/boda-velo-04-180.png")

    def test_sin_foto_la_portada_es_el_monograma_y_no_hay_velo(self):
        call_command("crear_demo_boda_velo", stdout=StringIO())
        invitacion = Invitacion.objects.get(slug="demo-boda-renata-tomas")
        invitacion.foto_portada = ""
        invitacion.save()
        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertContains(respuesta, 'class="portada-sin-foto"')
        self.assertNotContains(respuesta, 'id="velo"')
        self.assertNotContains(respuesta, "--foto-fondo: url(")


@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class FotoPortadaTests(TestCase):
    def setUp(self):
        call_command("crear_demo_boda_velo", stdout=StringIO())
        self.inv = Invitacion.objects.get(slug="demo-boda-renata-tomas")

    def test_si_no_hay_portada_se_usa_la_primera_foto_de_la_galeria(self):
        self.inv.foto_portada = ""
        self.inv.save()
        self.assertEqual(self.inv.foto_portada_src, "")
        segunda = ImagenGaleria.objects.create(invitacion=self.inv, imagen=foto_de_prueba("b.jpg", 40, 40), orden=2)
        primera = ImagenGaleria.objects.create(invitacion=self.inv, imagen=foto_de_prueba("a.jpg", 40, 40), orden=1)
        self.assertEqual(Invitacion.objects.get(pk=self.inv.pk).foto_portada_src, primera.imagen.url)
        self.assertNotEqual(primera.imagen.url, segunda.imagen.url)
        # la que se sube para la portada manda sobre la galería
        self.inv.foto_portada = foto_de_prueba("portada.jpg", 40, 60)
        self.inv.save()
        self.assertEqual(self.inv.foto_portada_src, self.inv.foto_portada.url)

    def test_cambiar_la_portada_borra_la_foto_vieja(self):
        vieja = Path(self.inv.foto_portada.path)
        self.assertTrue(vieja.exists())
        self.inv.foto_portada = foto_de_prueba("nueva.jpg", 40, 60)
        self.inv.save()
        self.assertFalse(vieja.exists())
        self.assertTrue(Path(self.inv.foto_portada.path).exists())

    def test_el_admin_achica_la_portada_y_le_quita_el_gps(self):
        admin = User.objects.create_superuser("dueno", "d@ejemplo.mx", "clave-larga-123")
        self.client.force_login(admin)
        url = reverse("admin:invitaciones_invitacion_change", args=[self.inv.pk])
        pagina = self.client.get(url)
        self.assertContains(pagina, 'name="foto_portada"')
        self.assertContains(pagina, f'<img src="{self.inv.foto_portada.url}"')     # vista previa
        self.assertContains(pagina, "«El Velo», «Frente al Mar», «Cajita Musical» y «Primer Latido»")   # la ayuda sale del catálogo

        datos = datos_del_admin(pagina, self.inv)
        datos["foto_portada"] = foto_de_prueba("IMG_2041.jpg", 2400, 3600)
        respuesta = self.client.post(url, datos)
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, "context", None)
                         and respuesta.context["adminform"].form.errors)
        self.inv.refresh_from_db()
        self.assertNotIn("IMG_2041", self.inv.foto_portada.name)
        with Image.open(self.inv.foto_portada.path) as guardada:
            self.assertEqual(max(guardada.size), LADO_MAXIMO_PORTADA)
            self.assertNotIn(0x8825, guardada.getexif())


@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class PedidoConFotoDePortadaTests(TestCase):
    def setUp(self):
        self.velo = Plantilla.objects.create(nombre="El Velo", tipo_evento="boda", slug_tema="boda-velo-04")
        self.pedido = Pedido.objects.create(cliente="Renata", plantilla=self.velo, nivel="interactiva")
        self.url = reverse("pedido", args=[self.pedido.token])

    def datos(self, **cambios):
        return {"anfitriones": "Renata & Tomás", "fecha": "2027-10-16", "hora": "17:30",
                "recepcion_nombre": "Hacienda Las Jacarandas", **cambios}

    def test_el_formulario_pide_la_foto_de_portada_solo_en_los_disenos_con_foto(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, "Foto de portada")
        self.assertContains(respuesta, 'name="foto_portada"')
        otra = Pedido.objects.create(cliente="Sofía", nivel="interactiva", plantilla=Plantilla.objects.create(
            nombre="Hotel Amor", tipo_evento="boda", slug_tema="boda-hotel-03"))
        self.assertNotContains(self.client.get(reverse("pedido", args=[otra.token])), 'name="foto_portada"')

    def test_la_portada_se_guarda_procesada_y_se_puede_cambiar(self):
        respuesta = self.client.post(self.url, self.datos(foto_portada=foto_de_prueba("boda.jpg", 3000, 4500)))
        self.assertRedirects(respuesta, f"{self.url}?listo=1")
        inv = Pedido.objects.get(pk=self.pedido.pk).invitacion
        primera = Path(inv.foto_portada.path)
        with Image.open(primera) as guardada:
            self.assertEqual(max(guardada.size), LADO_MAXIMO_PORTADA)
            self.assertNotIn(0x8825, guardada.getexif())
        self.assertEqual(inv.galeria.count(), 0)        # la portada no se mezcla con la galería
        # la vista previa ya la enseña bajo el velo
        self.assertContains(self.client.get(reverse("pedido_vista_previa", args=[self.pedido.token])),
                            f'class="portada-foto" src="{inv.foto_portada.url}"')

        # al volver al link la ve; corregir sin elegir otra la conserva; elegir otra reemplaza a la vieja
        self.assertContains(self.client.get(self.url), "Tu foto actual")
        self.client.post(self.url, self.datos(mensaje="Te esperamos"))
        inv.refresh_from_db()
        self.assertEqual(Path(inv.foto_portada.path), primera)
        self.client.post(self.url, self.datos(foto_portada=foto_de_prueba("otra.jpg", 800, 1200)))
        inv.refresh_from_db()
        self.assertFalse(primera.exists())
        self.assertTrue(Path(inv.foto_portada.path).exists())

    def test_un_archivo_que_no_es_foto_no_se_guarda(self):
        falso = SimpleUploadedFile("boda.jpg", b"no soy una foto", content_type="image/jpeg")
        respuesta = self.client.post(self.url, self.datos(foto_portada=falso))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "no se pudo abrir")
        self.assertIsNone(Pedido.objects.get(pk=self.pedido.pk).invitacion)


# ---------------------------------------------------------------------------
# Cajita Musical: los XV con la foto de la quinceañera en el espejo
# ---------------------------------------------------------------------------
@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class DemoCajitaMusicalTests(TestCase):
    def test_crear_demo_es_idempotente_y_la_foto_va_en_el_espejo(self):
        call_command("crear_demo_xv_cajita", stdout=StringIO())
        carpeta = Path(Invitacion.objects.get(slug="demo-xv-isabella").foto_portada.path).parent
        fotos_antes = set(os.listdir(carpeta))
        call_command("crear_demo_xv_cajita", "--host", "http://192.168.1.50:8000", stdout=StringIO())

        self.assertEqual(Plantilla.objects.filter(slug_tema="xv-cajita-04").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-xv-isabella")
        self.assertEqual(invitacion.plantilla.tipo_evento, "xv")
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 18)
        self.assertEqual(set(os.listdir(carpeta)), fotos_antes)    # la foto no se duplica

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/xv-cajita-04.html")
        # la foto en el espejo, el botón para darle cuerda (nace oculto), la medalla, el dije
        for fragmento in (f'<img src="{invitacion.foto_portada.url}" alt="Isabella"', 'id="dar-cuerda" hidden',
                          "Dale cuerda", "NOVIEMBRE", 'id="plantilla-dije"', "rsvp:enviado",
                          "Chambelán de honor", "Mi gran noche"):
            self.assertContains(respuesta, fragmento)
        self.assertContains(respuesta, "/static/invitaciones/pwa/xv-cajita-04-180.png")

    def test_sin_foto_el_espejo_muestra_la_inicial(self):
        call_command("crear_demo_xv_cajita", stdout=StringIO())
        invitacion = Invitacion.objects.get(slug="demo-xv-isabella")
        invitacion.foto_portada = ""
        invitacion.save()
        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertContains(respuesta, '<span class="espejo-inicial" aria-hidden="true">I</span>')
        self.assertNotContains(respuesta, 'fetchpriority="high"')

    def test_el_formulario_del_pedido_pide_la_foto_de_la_quinceanera(self):
        call_command("crear_demo_xv_cajita", stdout=StringIO())
        pedido = Pedido.objects.create(cliente="Mamá de Isabella", nivel="interactiva",
                                       plantilla=Plantilla.objects.get(slug_tema="xv-cajita-04"))
        respuesta = self.client.get(reverse("pedido", args=[pedido.token]))
        self.assertContains(respuesta, 'name="foto_portada"')
        self.assertContains(respuesta, "una foto de la quinceañera")


# ---------------------------------------------------------------------------
# Primer Latido: el baby shower con el ultrasonido en el monitor
# ---------------------------------------------------------------------------
@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class DemoPrimerLatidoTests(TestCase):
    def test_crear_demo_es_idempotente_y_el_eco_va_en_el_monitor(self):
        call_command("crear_demo_baby_latido", stdout=StringIO())
        carpeta = Path(Invitacion.objects.get(slug="demo-baby-andrea-pablo").foto_portada.path).parent
        fotos_antes = set(os.listdir(carpeta))
        call_command("crear_demo_baby_latido", "--host", "http://192.168.1.50:8000", stdout=StringIO())

        plantilla = Plantilla.objects.get(slug_tema="baby-shower-latido-04")
        self.assertTrue(plantilla.soporta_votacion)
        invitacion = Invitacion.objects.get(slug="demo-baby-andrea-pablo")
        self.assertEqual(set(os.listdir(carpeta)), fotos_antes)    # el eco no se duplica
        self.assertNotIn("bebe_nombre", invitacion.contenido_extra)  # hay votación: no se sabe si es niña o niño

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/baby-shower-latido-04.html")
        # el eco, el botón del latido (nace oculto), la fecha de parto para la semana,
        # la línea de latidos, la votación del motor y la pulsera del RSVP
        for fragmento in (f'<img src="{invitacion.foto_portada.url}" alt="Ultrasonido del bebé"', 'id="escuchar" hidden',
                          "Escuchar su corazón", f'data-fecha-parto="{invitacion.contenido_extra["fecha_probable_parto"]}"',
                          'class="trayecto"', 'id="votacion"', 'id="plantilla-pulsera"', "rsvp:enviado",
                          "Nuestro bebé viene en camino"):
            self.assertContains(respuesta, fragmento)
        self.assertContains(respuesta, "/static/invitaciones/pwa/baby-shower-latido-04-180.png")

    def test_sin_eco_el_monitor_muestra_un_corazon_y_sale_el_nombre_del_bebe(self):
        call_command("crear_demo_baby_latido", stdout=StringIO())
        invitacion = Invitacion.objects.get(slug="demo-baby-andrea-pablo")
        invitacion.foto_portada = ""
        invitacion.contenido_extra["bebe_nombre"] = "Emilia"
        invitacion.save()
        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertContains(respuesta, 'class="eco-corazon"')
        self.assertNotContains(respuesta, 'alt="Ultrasonido del bebé"')
        self.assertContains(respuesta, "Emilia viene en camino")
        self.assertContains(respuesta, "bebé Emilia")      # en la pulsera de visita

    def test_el_formulario_pide_recortar_los_datos_de_la_clinica(self):
        call_command("crear_demo_baby_latido", stdout=StringIO())
        pedido = Pedido.objects.create(cliente="Andrea", nivel="premium",
                                       plantilla=Plantilla.objects.get(slug_tema="baby-shower-latido-04"))
        respuesta = self.client.get(reverse("pedido", args=[pedido.token]))
        self.assertContains(respuesta, 'name="foto_portada"')
        self.assertContains(respuesta, "la foto del ultrasonido")
        self.assertContains(respuesta, "no salgan tu nombre ni los datos de la clínica")


# ---------------------------------------------------------------------------
# Frente al Mar: la boda en la playa, con la foto de los novios como el sol
# ---------------------------------------------------------------------------
@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class DemoFrenteAlMarTests(TestCase):
    def test_crear_demo_es_idempotente_y_la_foto_es_el_sol_del_atardecer(self):
        call_command("crear_demo_boda_mar", stdout=StringIO())
        carpeta = Path(Invitacion.objects.get(slug="demo-boda-natalia-iker").foto_portada.path).parent
        fotos_antes = set(os.listdir(carpeta))
        call_command("crear_demo_boda_mar", "--host", "http://192.168.1.50:8000", stdout=StringIO())

        self.assertEqual(Plantilla.objects.filter(slug_tema="boda-mar-05").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-boda-natalia-iker")
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 17)
        self.assertEqual(set(os.listdir(carpeta)), fotos_antes)    # la foto no se duplica

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/boda-mar-05.html")
        src = invitacion.foto_portada.url
        # la foto como sol (con los nombres de alt) y como reflejo, el destino bajo la fecha,
        # el mensaje en "El gran día", la sombra de palmera y la botella del RSVP
        for fragmento in (f'<img src="{src}" alt="Natalia &amp; Iker"', f'--foto-sol: url("{src}")',
                          'class="escena"', 'class="reflejo"', '<p class="portada-destino">Tulum, Quintana Roo</p>',
                          '<blockquote class="cita">Nos conocimos', "boda-mar-palma.svg", 'id="plantilla-botella"',
                          "te esperamos frente al mar", "rsvp:enviado", "Nos casamos frente al mar"):
            self.assertContains(respuesta, fragmento)
        self.assertContains(respuesta, "/static/invitaciones/pwa/boda-mar-05-180.png")

    def test_sin_foto_el_sol_lleva_las_iniciales(self):
        call_command("crear_demo_boda_mar", stdout=StringIO())
        invitacion = Invitacion.objects.get(slug="demo-boda-natalia-iker")
        invitacion.foto_portada = ""
        invitacion.mensaje_bienvenida = ""
        del invitacion.contenido_extra["ciudad"]
        invitacion.save()
        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertContains(respuesta, "sol-sin-foto")
        self.assertContains(respuesta, 'class="sol-iniciales" data-iniciales')
        self.assertNotContains(respuesta, "--foto-sol: url(")
        self.assertNotContains(respuesta, 'class="portada-destino"')
        self.assertNotContains(respuesta, 'class="cita"')

    def test_el_formulario_pide_el_destino_y_una_foto_para_el_circulo(self):
        plantilla = Plantilla.objects.create(nombre="Frente al Mar", tipo_evento="boda", slug_tema="boda-mar-05")
        pedido = Pedido.objects.create(cliente="Natalia", plantilla=plantilla, nivel="interactiva")
        url = reverse("pedido", args=[pedido.token])
        respuesta = self.client.get(url)
        self.assertContains(respuesta, 'name="foto_portada"')
        self.assertContains(respuesta, "se verá en un círculo")
        self.assertContains(respuesta, "Destino")
        self.assertContains(respuesta, "Ej. Tulum, Quintana Roo")

        self.client.post(url, {"anfitriones": "Natalia & Iker", "fecha": "2027-11-13", "hora": "17:00",
                               "recepcion_nombre": "Casa Arena", "ciudad": "Tulum, Quintana Roo"})
        inv = Pedido.objects.get(pk=pedido.pk).invitacion
        self.assertEqual(inv.contenido_extra["ciudad"], "Tulum, Quintana Roo")

        # La Gira sigue pidiendo la ciudad con su propio texto
        gira = Pedido.objects.create(cliente="Ximena", nivel="interactiva", plantilla=Plantilla.objects.create(
            nombre="La Gira", tipo_evento="xv", slug_tema="xv-gira-03"))
        self.assertContains(self.client.get(reverse("pedido", args=[gira.token])), "Sale en el boleto de la gira.")


# ---------------------------------------------------------------------------
# Mención Honorífica: la graduación como tesis empastada que se abre
# ---------------------------------------------------------------------------
class DemoMencionHonorificaTests(TestCase):
    def test_crear_demo_es_idempotente_y_llega_como_tesis_cerrada(self):
        call_command("crear_demo_graduacion_tesis", stdout=StringIO())
        call_command("crear_demo_graduacion_tesis", "--host", "http://192.168.1.50:8000", stdout=StringIO())

        self.assertEqual(Plantilla.objects.filter(slug_tema="graduacion-tesis-04").count(), 1)
        invitacion = Invitacion.objects.get(slug="demo-graduacion-fernando")
        self.assertEqual(timezone.localtime(invitacion.fecha_evento).hour, 18)

        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "invitaciones/temas/graduacion-tesis-04.html")
        # la tapa (nace oculta), el texto de tesis, el sello con la generación, el mensaje con
        # capitular en el Capítulo I, la tabla y el voto aprobatorio del RSVP
        for fragmento in ('id="tapa" hidden', "Abrir la tesis", "De las aulas al foro: memoria de un sueño cumplido",
                          "que para concluir sus estudios de", "Licenciatura en Derecho",
                          "Benemérita Universidad Autónoma de Puebla", 'href="#arco-tapa"', "Generación 2022 — 2027",
                          '<p class="parrafo-inicial">Cinco años', "Tabla 1.", 'id="plantilla-voto"',
                          "Voto aprobatorio", "rsvp:enviado", '--anio: "2027"'):
            self.assertContains(respuesta, fragmento)
        self.assertContains(respuesta, "/static/invitaciones/pwa/graduacion-tesis-04-180.png")

    def test_sin_titulo_ni_carrera_la_tesis_se_arma_igual(self):
        call_command("crear_demo_graduacion_tesis", stdout=StringIO())
        invitacion = Invitacion.objects.get(slug="demo-graduacion-fernando")
        invitacion.contenido_extra = {}
        invitacion.mensaje_bienvenida = ""
        invitacion.save()
        respuesta = self.client.get(reverse("invitaciones:detalle", args=[invitacion.slug]))
        self.assertContains(respuesta, "Memoria de un sueño cumplido")
        self.assertContains(respuesta, "Generación 2027")             # el sello usa el año
        self.assertNotContains(respuesta, "que para concluir sus estudios de")
        self.assertNotContains(respuesta, 'class="parrafo-inicial"')

    def test_el_formulario_pide_el_titulo_de_la_tesis_solo_en_este_diseno(self):
        plantilla = Plantilla.objects.create(nombre="Mención Honorífica", tipo_evento="graduacion",
                                             slug_tema="graduacion-tesis-04")
        pedido = Pedido.objects.create(cliente="Fernando", plantilla=plantilla, nivel="interactiva")
        url = reverse("pedido", args=[pedido.token])
        self.assertContains(self.client.get(url), "Título de tu «tesis»")
        self.client.post(url, {"anfitriones": "Fernando Ibarra", "fecha": "2027-06-26", "hora": "18:00",
                               "lugar_nombre": "Hacienda San Bartolo", "titulo_tesis": "De las aulas al foro"})
        inv = Pedido.objects.get(pk=pedido.pk).invitacion
        self.assertEqual(inv.contenido_extra["titulo_tesis"], "De las aulas al foro")
        self.assertContains(self.client.get(url), 'value="De las aulas al foro"')    # al volver, ya está lleno

        laurel = Pedido.objects.create(cliente="Valeria", nivel="interactiva", plantilla=Plantilla.objects.create(
            nombre="Laurel de Oro", tipo_evento="graduacion", slug_tema="graduacion-editorial-01"))
        self.assertNotContains(self.client.get(reverse("pedido", args=[laurel.token])), "Título de tu «tesis»")


# ---------------------------------------------------------------------------
# Catálogo: panel en vivo, diseños a la medida y el contador en singular
# ---------------------------------------------------------------------------
class CatalogoVentaTests(TestCase):
    def test_el_catalogo_presume_el_panel_y_ofrece_disenos_a_la_medida(self):
        respuesta = self.client.get("/")
        for texto in ('id="panel"', "Tu panel <em>en vivo</em>", "Tu lista en Excel",
                      'id="a-tu-medida"', "Ajustamos uno del catálogo", "Un diseño totalmente nuevo",
                      "¿Pueden hacer un diseño que no está en el catálogo?", "¿Puedo corregir mis datos"):
            self.assertContains(respuesta, texto)
        self.assertNotContains(respuesta, "Te compartimos la lista")     # el texto viejo, antes del panel
        # cada opción abre WhatsApp con su mensaje ya escrito
        self.assertIn("dise%C3%B1o%20totalmente%20nuevo", respuesta.context["whatsapp_nueva"])
        self.assertIn("cambiarle%20algunas%20cosas", respuesta.context["whatsapp_ajustar"])

    def test_el_contador_del_rsvp_cambia_a_singular_con_una_persona(self):
        call_command("crear_demo_baby_shower", stdout=StringIO())
        respuesta = self.client.get(reverse("invitaciones:detalle", args=["demo-baby-mariana-diego"]))
        self.assertContains(respuesta, '<span id="texto-confirmados">personas ya confirmaron</span>')
        self.assertContains(respuesta, "'persona ya confirmó'")
