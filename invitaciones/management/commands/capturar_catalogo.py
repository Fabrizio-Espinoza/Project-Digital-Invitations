"""
Toma la captura de la portada de cada demo para la página de catálogo.

Uso (con el servidor corriendo en otra terminal y los demos creados):
    python manage.py runserver
    python manage.py capturar_catalogo
    python manage.py capturar_catalogo --solo xv-gira-03     # solo uno

Necesita Playwright, que NO va en requirements.txt porque el servidor no lo
usa (solo tu compu, cuando agregas una plantilla):
    pip install playwright
    playwright install chromium

Deja static/invitaciones/catalogo/<slug_tema>.webp (tamaño de celular a 2x,
recortado a 540 px de ancho) y la imagen para compartir en WhatsApp
static/invitaciones/catalogo/compartir.jpg (1200 × 630, lo que pide
Open Graph). Después: git add, commit y en el servidor collectstatic.
"""
import io
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from PIL import Image

from invitaciones.catalogo import DISENOS

CARPETA = Path(__file__).resolve().parents[2] / "static" / "invitaciones" / "catalogo"
ANCHO_CELULAR, ALTO_CELULAR = 390, 844       # iPhone 12-15
ANCHO_FINAL = 540
FONDO_COMPARTIR = (247, 242, 236)           # --papel del catálogo
# Los de la imagen para compartir: un evento distinto cada uno y el del centro
# es el que queda si WhatsApp la recorta a cuadrado.
PARA_COMPARTIR = ["La Gira", "Terracota Velada", "Próxima Salida", "La Lotería", "Pancito en el Horno"]


class Command(BaseCommand):
    help = "Captura la portada de cada demo para la página de catálogo."

    def add_arguments(self, parser):
        parser.add_argument("--host", default="http://127.0.0.1:8000", help="Dónde está corriendo el servidor.")
        parser.add_argument("--solo", default=None, help="slug_tema de un solo diseño.")
        parser.add_argument("--espera", type=float, default=3.5,
                            help="Segundos para que terminen las animaciones de entrada.")
        parser.add_argument("--chromium", default=None,
                            help="Ruta a un Chromium ya instalado (si no, usa el de Playwright).")

    def handle(self, *args, **opciones):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise CommandError("Falta Playwright: pip install playwright && playwright install chromium")

        host = opciones["host"].rstrip("/")
        disenos = [d for d in DISENOS if not opciones["solo"] or d["slug_tema"] == opciones["solo"]]
        if not disenos:
            raise CommandError(f"No hay ningún diseño con slug_tema {opciones['solo']!r}.")
        CARPETA.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            navegador = p.chromium.launch(executable_path=opciones["chromium"])
            contexto = navegador.new_context(
                viewport={"width": ANCHO_CELULAR, "height": ALTO_CELULAR},
                device_scale_factor=2, is_mobile=True, has_touch=True, locale="es-MX",
                timezone_id="America/Mexico_City", service_workers="block",
            )
            for diseno in disenos:
                pagina = contexto.new_page()
                respuesta = pagina.goto(f"{host}/invitaciones/{diseno['demo']}/", wait_until="networkidle")
                if not respuesta or respuesta.status != 200:
                    raise CommandError(f"{diseno['demo']} no abrió (¿corriste crear_todos_los_demos?).")
                pagina.evaluate("document.fonts.ready.then(() => true)")
                time.sleep(opciones["espera"])
                png = pagina.screenshot()
                pagina.close()

                imagen = Image.open(io.BytesIO(png)).convert("RGB")
                alto = round(imagen.height * ANCHO_FINAL / imagen.width)
                imagen = imagen.resize((ANCHO_FINAL, alto), Image.LANCZOS)
                destino = CARPETA / f"{diseno['slug_tema']}.webp"
                imagen.save(destino, "WEBP", quality=82, method=6)
                self.stdout.write(f"  {diseno['nombre']:<22} {destino.stat().st_size // 1024} KB")
            navegador.close()

        self._imagen_para_compartir()
        self.stdout.write(self.style.SUCCESS(f"Listo: {CARPETA}"))

    def _imagen_para_compartir(self):
        """Cinco celulares de eventos distintos, alternados, en 1200 × 630."""
        lienzo = Image.new("RGB", (1200, 630), FONDO_COMPARTIR)
        por_nombre = {d["nombre"]: d for d in DISENOS}
        ancho, separacion, marco = 236, 236, 6
        x = (1200 - (separacion * (len(PARA_COMPARTIR) - 1) + ancho)) // 2
        for i, nombre in enumerate(PARA_COMPARTIR):
            archivo = CARPETA / f"{por_nombre[nombre]['slug_tema']}.webp"
            if not archivo.exists():
                return
            celular = Image.open(archivo).convert("RGB")
            celular = celular.resize((ancho, round(celular.height * ancho / celular.width)), Image.LANCZOS)
            y = 40 if i % 2 else 70          # alternados, como si los sostuvieran
            borde = Image.new("RGB", (ancho + 2 * marco, celular.height + 2 * marco), (27, 23, 20))
            borde.paste(celular, (marco, marco))
            lienzo.paste(borde, (x + i * separacion - marco, y))
        lienzo.save(CARPETA / "compartir.jpg", "JPEG", quality=85, optimize=True)
