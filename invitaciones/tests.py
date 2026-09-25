from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from .models import Invitacion, Plantilla


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
