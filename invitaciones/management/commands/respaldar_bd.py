"""
Respaldo de la base de datos (y opcionalmente de las fotos subidas).

Uso:
    python manage.py respaldar_bd                 # solo la base
    python manage.py respaldar_bd --fotos         # base + carpeta media/
    python manage.py respaldar_bd --conservar 30  # cuántos respaldos guardar

Deja archivos con fecha en RESPALDOS_DIR (carpeta "respaldos/"):
    bd-2026-09-30_0300.sqlite3.gz
    fotos-2026-09-30_0300.tar.gz

Por qué así:
- No se copia db.sqlite3 "a mano": si alguien confirma justo en ese
  instante, la copia puede quedar corrupta. SQLite trae su propia función
  de respaldo, que saca una copia consistente aunque el sitio esté en uso.
- Cada copia se revisa (PRAGMA integrity_check) antes de guardarla: un
  respaldo que no sirve es peor que no tener, porque da falsa tranquilidad.
- Se conservan los N más recientes y se borran los viejos, para no llenar
  el disco del servidor.

Restaurar: ver DESPLIEGUE.md ("Restaurar un respaldo").
"""
import gzip
import shutil
import sqlite3
import tarfile
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Respalda la base de datos SQLite (y las fotos con --fotos) en RESPALDOS_DIR."

    def add_arguments(self, parser):
        parser.add_argument("--fotos", action="store_true", help="Incluye la carpeta media/ (fotos de galería).")
        parser.add_argument("--conservar", type=int, default=14, help="Respaldos de cada tipo a conservar (14).")
        parser.add_argument("--destino", default=None, help="Carpeta destino (por defecto RESPALDOS_DIR).")

    def handle(self, *args, **opciones):
        base = settings.DATABASES["default"]
        if base["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("Este comando es para SQLite. Con PostgreSQL usa pg_dump.")

        destino = Path(opciones["destino"] or settings.RESPALDOS_DIR)
        destino.mkdir(parents=True, exist_ok=True)
        sello = timezone.localtime().strftime("%Y-%m-%d_%H%M%S")

        archivo_bd = self._respaldar_sqlite(Path(base["NAME"]), destino / f"bd-{sello}.sqlite3.gz")
        self.stdout.write(self.style.SUCCESS(f"Base respaldada: {archivo_bd} ({self._tamano(archivo_bd)})"))

        if opciones["fotos"]:
            archivo_fotos = self._respaldar_fotos(Path(settings.MEDIA_ROOT), destino / f"fotos-{sello}.tar.gz")
            if archivo_fotos:
                self.stdout.write(self.style.SUCCESS(f"Fotos respaldadas: {archivo_fotos} ({self._tamano(archivo_fotos)})"))
            else:
                self.stdout.write("No hay carpeta de fotos todavía; se omitió.")

        for prefijo in ("bd-", "fotos-"):
            self._rotar(destino, prefijo, opciones["conservar"])

    def _respaldar_sqlite(self, origen, archivo):
        if not origen.exists():
            raise CommandError(f"No existe la base de datos {origen}.")
        with tempfile.TemporaryDirectory() as carpeta:
            copia = Path(carpeta) / "copia.sqlite3"
            # API de respaldo de SQLite: copia consistente con el sitio funcionando
            fuente = sqlite3.connect(origen)
            destino = sqlite3.connect(copia)
            try:
                fuente.backup(destino)
                resultado = destino.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                destino.close()
                fuente.close()
            if resultado != "ok":
                raise CommandError(f"La copia no pasó la revisión de integridad: {resultado}")
            with open(copia, "rb") as entrada, gzip.open(archivo, "wb") as salida:
                shutil.copyfileobj(entrada, salida)
        return archivo

    def _respaldar_fotos(self, carpeta_media, archivo):
        if not carpeta_media.exists():
            return None
        with tarfile.open(archivo, "w:gz") as tar:
            tar.add(carpeta_media, arcname="media")
        return archivo

    def _rotar(self, destino, prefijo, conservar):
        respaldos = sorted(destino.glob(f"{prefijo}*"), reverse=True)   # el nombre lleva la fecha
        for viejo in respaldos[max(conservar, 1):]:
            viejo.unlink()
            self.stdout.write(f"Borrado respaldo viejo: {viejo.name}")

    @staticmethod
    def _tamano(archivo):
        kb = archivo.stat().st_size / 1024
        return f"{kb:.0f} KB" if kb < 1024 else f"{kb / 1024:.1f} MB"
