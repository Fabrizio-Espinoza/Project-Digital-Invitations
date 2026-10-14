import secrets
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.text import slugify
import uuid

# Canción de la invitación: formatos que suenan en iPhone y Android
FORMATOS_CANCION = ["mp3", "m4a", "aac"]
MAX_MB_CANCION = 15


def _ruta_cancion(instancia, nombre):
    # nombre al azar: sin espacios, acentos ni el nombre del cliente en la URL pública
    return f"invitaciones/musica/{uuid.uuid4().hex[:12]}{Path(nombre).suffix.lower()}"


def _ruta_portada(instancia, nombre):
    # igual que la canción: nombre al azar (la foto ya llega procesada como JPEG)
    return f"invitaciones/portadas/{uuid.uuid4().hex[:12]}{Path(nombre).suffix.lower() or '.jpg'}"


def validar_cancion(archivo):
    """
    Que sea de verdad un audio y no muy pesado. Se revisan los primeros
    bytes (no basta con que el nombre termine en .mp3): MP3 empieza con
    "ID3" o con la marca de cuadro 0xFFE…, y M4A/AAC lleva "ftyp" en el byte 4.
    """
    if archivo.size > MAX_MB_CANCION * 1024 * 1024:
        raise ValidationError(f"La canción pesa más de {MAX_MB_CANCION} MB. Usa un MP3 normal (128–192 kbps).")
    archivo.seek(0)
    inicio = archivo.read(12)
    archivo.seek(0)
    es_mp3 = inicio[:3] == b"ID3" or (len(inicio) > 1 and inicio[0] == 0xFF and inicio[1] & 0xE0 == 0xE0)
    es_m4a = inicio[4:8] == b"ftyp"
    if not (es_mp3 or es_m4a):
        raise ValidationError("Ese archivo no parece una canción. Sube un MP3 o M4A.")


class Plantilla(models.Model):
    """
    Representa un DISEÑO reutilizable (boda elegante, XV vibrante, etc).
    No guarda datos de un cliente en particular — solo define qué tan
    'pintado' está cada estilo y qué features soporta por defecto.
    Esto te permite lanzar plantillas nuevas sin tocar el modelo Invitacion.
    """
    TIPO_EVENTO = [
        ("boda", "Boda"),
        ("xv", "XV Años"),
        ("graduacion", "Graduación"),
        ("evento", "Evento general"),
        ("fiesta", "Fiesta"),
        ("baby_shower", "Baby Shower"),
    ]

    nombre = models.CharField(max_length=100)
    tipo_evento = models.CharField(max_length=20, choices=TIPO_EVENTO)
    slug_tema = models.SlugField(unique=True)  # ej. "boda-minimal-01" -> referencia a la carpeta de CSS/HTML
    soporta_rsvp = models.BooleanField(default=True)
    soporta_musica = models.BooleanField(default=True)
    soporta_galeria = models.BooleanField(default=True)
    # default=False a propósito: la votación solo aparece en plantillas cuyo CSS
    # ya sabe dibujarla. Las plantillas existentes (boda) quedan igual que antes.
    soporta_votacion = models.BooleanField(default=False)
    vista_previa_url = models.URLField(blank=True)
    # Color de fondo del diseño en hex (ej. "#FBF6F0"). Lo usa la PWA para
    # pintar la barra de estado del celular y la pantalla de carga al abrir
    # la invitación desde el ícono, así no hay un "flash" de otro color.
    color_tema = models.CharField(max_length=7, default="#FFFFFF")

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_evento_display()})"


def _token_privado():
    # 12 caracteres al azar (~72 bits): imposible de adivinar, corto para WhatsApp
    return secrets.token_urlsafe(9)


# nombre viejo: lo usa la migración 0004
_token_pedido = _token_privado


class Invitacion(models.Model):
    """
    Una invitación comprada por un cliente. Aquí vive TODO lo que varía
    por cliente: nombres, fecha, textos. El diseño en sí vive en Plantilla.
    """
    NIVEL = [
        ("imagen", "Solo imagen / PDF"),      # pedido simple, sin sitio interactivo
        ("interactiva", "Interactiva"),        # countdown + RSVP + galería
        ("premium", "Premium"),                # interactiva + música + extras
    ]

    # UUID además del slug: el slug es la URL pública y editable a futuro,
    # el UUID es el identificador interno estable (nunca cambia aunque
    # renombres el slug).
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True, max_length=80)

    plantilla = models.ForeignKey(Plantilla, on_delete=models.PROTECT, related_name="invitaciones")
    nivel = models.CharField(max_length=20, choices=NIVEL, default="interactiva")

    # Datos comunes a cualquier tipo de evento
    titulo_evento = models.CharField(max_length=150)          # "Boda de Ana & Luis"
    anfitriones = models.CharField(max_length=200)             # nombres principales
    fecha_evento = models.DateTimeField()
    lugar_nombre = models.CharField(max_length=200, blank=True)
    lugar_mapa_url = models.URLField(blank=True)
    mensaje_bienvenida = models.TextField(blank=True)

    # Features opcionales (solo aplican si nivel/plantilla las soporta)
    musica_url = models.URLField(
        "Música (link)", blank=True,
        help_text="Solo si la canción ya está en internet (link directo a un .mp3). Si subes el archivo, se usa el archivo.",
    )
    musica_archivo = models.FileField(
        "Canción", upload_to=_ruta_cancion, blank=True,
        validators=[FileExtensionValidator(FORMATOS_CANCION), validar_cancion],
        help_text=f"MP3 o M4A, máximo {MAX_MB_CANCION} MB. Suena con el botón de música (solo paquete Premium).",
    )
    fecha_limite_rsvp = models.DateField(null=True, blank=True)
    # La foto de los novios / festejados que abre la invitación en los diseños
    # con foto en la portada (ej. El Velo). Se sube ya derecha, achicada y sin
    # EXIF (ver fotos.preparar_foto, la usan el formulario del cliente y el admin).
    foto_portada = models.ImageField(
        "Foto de portada", upload_to=_ruta_portada, blank=True,
        help_text="La usan los diseños con foto en la portada (El Velo). Vertical se ve mejor. "
                  "Si no hay, se usa la primera foto de la galería.",
    )

    # contenido_extra: aquí va todo lo que cambia según el TIPO de evento
    # (padrinos en una boda, mesa de regalos, código de vestimenta, etc.)
    # Usar JSONField en vez de una columna por cada campo posible evita que
    # el modelo crezca infinito cada vez que agregues un tipo de evento nuevo.
    contenido_extra = models.JSONField(default=dict, blank=True)

    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    # Link privado del panel del anfitrión (/panel/<token>/): ahí ve quién
    # confirmó y descarga la lista. Distinto del slug público a propósito.
    token_panel = models.CharField(max_length=24, unique=True, default=_token_privado, editable=False)

    # archivos que son solo de esta invitación: al reemplazarlos se borra el viejo
    ARCHIVOS_PROPIOS = ("musica_archivo", "foto_portada")

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.titulo_evento)[:60]
            self.slug = f"{base}-{uuid.uuid4().hex[:6]}"
        # si cambiaron o quitaron la canción o la foto de portada, el archivo
        # viejo se borra del disco (Django no lo hace solo y cada MP3 pesa varios MB)
        anteriores = {}
        if not self._state.adding:
            anteriores = Invitacion.objects.filter(pk=self.pk).values(*self.ARCHIVOS_PROPIOS).first() or {}
        super().save(*args, **kwargs)
        for campo in self.ARCHIVOS_PROPIOS:
            archivo = getattr(self, campo)
            if anteriores.get(campo) and anteriores[campo] != archivo.name:
                archivo.storage.delete(anteriores[campo])

    def __str__(self):
        return f"{self.titulo_evento} ({self.slug})"

    @property
    def musica_src(self):
        """
        La URL que usa el <audio>. Si subieron el archivo, ese manda.
        Si no, el link: si la canción vive en nuestro propio
        /static/ (ej. http://192.168.1.50:8000/static/.../cancion.mp3), se
        devuelve solo la ruta: así suena igual abierta por la IP de la compu,
        por localhost, por un túnel HTTPS o en el servidor final, sin tener
        que volver a capturar la URL cuando cambia la IP o el dominio.
        Una canción de otro sitio (https://...) se deja tal cual.
        """
        if self.musica_archivo:
            return self.musica_archivo.url
        partes = urlsplit(self.musica_url or "")
        ruta_static = "/" + settings.STATIC_URL.lstrip("/")
        if partes.path.startswith(ruta_static):
            return partes.path
        return self.musica_url

    @property
    def foto_portada_src(self):
        """
        La foto de la portada: la que subieron para eso o, si no hay, la
        primera de la galería (con prefetch_related("galeria") no cuesta
        otra consulta). Vacío si no hay ninguna: la plantilla usa su portada sin foto.
        """
        if self.foto_portada:
            return self.foto_portada.url
        fotos = list(self.galeria.all()[:1]) if self.pk else []
        return fotos[0].imagen.url if fotos else ""


class ImagenGaleria(models.Model):
    """
    Fotos de la galería. Modelo aparte (en vez de una lista en JSON) para
    que puedas reordenar, borrar o subir imágenes desde el admin de Django
    sin tocar código, y para poder guardar el archivo real, no solo una URL.
    """
    invitacion = models.ForeignKey(Invitacion, on_delete=models.CASCADE, related_name="galeria")
    imagen = models.ImageField(upload_to="invitaciones/galeria/")
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden"]


class Confirmacion(models.Model):
    """
    Cada respuesta de RSVP. Se relaciona a una Invitacion específica,
    así que el conteo en tiempo real es simplemente un COUNT filtrado
    por invitacion + asistencia="si".
    """
    ASISTENCIA = [
        ("si", "Sí asistiré"),
        ("no", "No podré asistir"),
        ("tal_vez", "Tal vez"),
    ]

    invitacion = models.ForeignKey(Invitacion, on_delete=models.CASCADE, related_name="confirmaciones")
    nombre_invitado = models.CharField(max_length=150)
    asistencia = models.CharField(max_length=10, choices=ASISTENCIA)
    num_acompanantes = models.PositiveSmallIntegerField(default=0)
    mensaje = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada_en"]


class Voto(models.Model):
    """
    Cada predicción del juego de votación en vivo (ej. "¿Niña o niño?" en un
    baby shower). La opción se guarda como texto — la 'clave' definida en
    invitacion.contenido_extra["votacion"]["opciones"] — en vez de choices
    fijas: así cada invitación define sus propias opciones sin migraciones,
    igual que el resto de datos por tipo de evento.
    """
    invitacion = models.ForeignKey(Invitacion, on_delete=models.CASCADE, related_name="votos")
    opcion = models.CharField(max_length=40)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]



class Pedido(models.Model):
    """
    Un cliente que ya pagó y tiene que mandar sus datos. Tú lo creas en el
    admin (diseño + paquete) y le mandas el link privado /pedido/<token>/;
    el cliente llena el formulario desde su celular y al enviarlo se crea
    su Invitacion como borrador (activa=False) para que la revises y la
    publiques. Mientras no la publiques, el cliente puede corregir sus datos.
    """
    token = models.CharField(max_length=24, unique=True, default=_token_privado, editable=False)
    cliente = models.CharField(max_length=120, help_text="Para ti: cómo identificas a este cliente (no se publica).")
    plantilla = models.ForeignKey(Plantilla, on_delete=models.PROTECT, related_name="pedidos")
    nivel = models.CharField(max_length=20, choices=Invitacion.NIVEL, default="interactiva")
    invitacion = models.OneToOneField(
        Invitacion, on_delete=models.SET_NULL, null=True, blank=True, related_name="pedido"
    )
    # lo que el cliente pide y no cabe en la invitación
    cancion = models.CharField(max_length=300, blank=True)
    notas = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    enviado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.cliente} · {self.plantilla.nombre}"

    @property
    def abierto(self):
        """El cliente puede llenar/corregir hasta que la invitación se publica."""
        return self.invitacion is None or not self.invitacion.activa
