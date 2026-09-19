from django.db import models
from django.utils.text import slugify
import uuid


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
    ]

    nombre = models.CharField(max_length=100)
    tipo_evento = models.CharField(max_length=20, choices=TIPO_EVENTO)
    slug_tema = models.SlugField(unique=True)  # ej. "boda-minimal-01" -> referencia a la carpeta de CSS/HTML
    soporta_rsvp = models.BooleanField(default=True)
    soporta_musica = models.BooleanField(default=True)
    soporta_galeria = models.BooleanField(default=True)
    vista_previa_url = models.URLField(blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_evento_display()})"


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
    musica_url = models.URLField(blank=True)
    fecha_limite_rsvp = models.DateField(null=True, blank=True)

    # contenido_extra: aquí va todo lo que cambia según el TIPO de evento
    # (padrinos en una boda, mesa de regalos, código de vestimenta, etc.)
    # Usar JSONField en vez de una columna por cada campo posible evita que
    # el modelo crezca infinito cada vez que agregues un tipo de evento nuevo.
    contenido_extra = models.JSONField(default=dict, blank=True)

    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.titulo_evento)[:60]
            self.slug = f"{base}-{uuid.uuid4().hex[:6]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.titulo_evento} ({self.slug})"


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