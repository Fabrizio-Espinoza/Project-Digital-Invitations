"""
Fotos que suben los clientes (galería y foto de portada).

Vive aparte de pedidos.py porque la usan el formulario del cliente Y el admin
(models.py no puede importar pedidos.py: pedidos.py ya importa models.py).
"""
import uuid
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_MB_FOTO = 15
# px: un celular pinta la galería a ~390 px × 3 de densidad ≈ 1200 px; 1600 da margen
# para ampliar y pesa ~40 % menos que 2000 (unos 180 KB por foto)
LADO_MAXIMO_FOTO = 1600
# la portada llena toda la pantalla (844 px de alto × 3 de densidad): un poco más grande
LADO_MAXIMO_PORTADA = 2000
CALIDAD_JPEG = 82


def preparar_foto(archivo, lado_maximo=LADO_MAXIMO_FOTO):
    """
    Revisa que sea una foto de verdad y la deja lista para la invitación:
    derecha (los celulares la guardan "acostada" con una etiqueta EXIF),
    máximo lado_maximo px por lado y en JPEG. Al volver a guardarla se quitan los
    datos EXIF, que en fotos de celular incluyen la ubicación GPS de la casa.
    """
    if archivo.size > MAX_MB_FOTO * 1024 * 1024:
        raise ValidationError(f"«{archivo.name}» pesa más de {MAX_MB_FOTO} MB.")
    try:
        with Image.open(archivo) as imagen:
            imagen.verify()
        archivo.seek(0)
        with Image.open(archivo) as imagen:
            imagen = ImageOps.exif_transpose(imagen).convert("RGB")
            imagen.thumbnail((lado_maximo, lado_maximo), Image.LANCZOS)
            salida = BytesIO()
            imagen.save(salida, "JPEG", quality=CALIDAD_JPEG, optimize=True, progressive=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError(f"«{archivo.name}» no se pudo abrir. Usa fotos JPG o PNG.")
    return ContentFile(salida.getvalue(), name=f"{uuid.uuid4().hex[:12]}.jpg")
