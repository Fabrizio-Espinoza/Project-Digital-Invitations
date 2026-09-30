"""
Formulario que llena el CLIENTE para armar su invitación (/pedido/<token>/).

La idea: que nadie escriba JSON a mano. El formulario pregunta según el tipo
de evento (una boda pide ceremonia y recepción; un baby shower, la fecha de
parto) y según el diseño (La Gira pide la ciudad, La Lotería el número de
la carta), y al final lo convierte en una Invitacion con su contenido_extra
armado con las mismas claves que ya usan las plantillas.

Tres piezas:
- FormularioPedido: campos sueltos (nombres, fecha, lugares…) con la
  validación normal de Django, agrupados en secciones para pintarlos.
- Filas repetibles (programa, padrinos, mesas de regalos): se mandan como
  listas en el POST (itinerario-hora, itinerario-evento…) y las lee leer_filas.
- guardar_pedido: crea o actualiza la Invitacion (siempre como borrador).
"""
import uuid
from datetime import datetime
from io import BytesIO

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import URLValidator
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import ImagenGaleria, Invitacion

MAX_FOTOS = 12
MAX_MB_FOTO = 15
LADO_MAXIMO_FOTO = 2000    # px: se ve nítida en cualquier celular y pesa ~300 KB

# ------------------------------------------------------------------
# Textos que cambian según el tipo de evento
# ------------------------------------------------------------------
ANFITRIONES = {
    "boda": ("Nombres de los novios", "Ej. Daniela & Andrés"),
    "xv": ("Nombre de la quinceañera", "Ej. Ximena"),
    "graduacion": ("Nombre de quien se gradúa", "Ej. Camila Torres"),
    "fiesta": ("Nombre del festejado o la festejada", "Ej. Rodrigo"),
    "baby_shower": ("Nombres de los papás", "Ej. Mariana & Diego"),
    "evento": ("¿Quién organiza?", "Ej. Familia Hernández"),
}
TITULO_AUTOMATICO = {
    "boda": "Boda de {}",
    "xv": "XV años de {}",
    "graduacion": "Graduación de {}",
    "fiesta": "Fiesta de {}",
    "baby_shower": "Baby shower de {}",
    "evento": "{}",
}
MENSAJE_EJEMPLO = {
    "boda": "Ej. Con la alegría de nuestras familias, queremos compartir contigo el día en que unimos nuestras vidas.",
    "xv": "Ej. Hay momentos que se viven una sola vez. Quiero que estés conmigo en esta noche tan especial.",
    "graduacion": "Ej. Después de años de esfuerzo, llegó el momento de celebrar. Me encantaría que fueras parte.",
    "fiesta": "Ej. Treinta vueltas al sol merecen una noche que no se olvide. ¡Ven a celebrar conmigo!",
    "baby_shower": "Ej. Con el corazón lleno de ilusión te invitamos a celebrar la llegada de nuestro bebé.",
    "evento": "Un mensaje corto para tus invitados.",
}

# Programa, familia y mesas de regalos: filas que el cliente agrega con un botón.
# (clave del campo, etiqueta, ejemplo, largo máximo)
REPETIBLES = {
    "itinerario": {
        "titulo": "Programa del evento",
        "ayuda": "Opcional. Lo que va pasando y a qué hora.",
        "campos": [("hora", "Hora", "7:00 PM", 20), ("evento", "¿Qué pasa?", "Cena", 120)],
        "obligatorio": "evento",
        "maximo": 15,
        "agregar": "Agregar otro momento",
    },
    "padrinos": {
        "titulo": "Papás y padrinos",
        "ayuda": "Opcional. Un renglón por grupo: padres de la novia, padrinos de anillos…",
        "campos": [("rol", "¿Quiénes son?", "Padrinos de anillos", 80), ("nombres", "Nombres", "Ana & Jorge Salas", 150)],
        "obligatorio": "nombres",
        "maximo": 12,
        "agregar": "Agregar otro grupo",
    },
    "mesas_regalos": {
        "titulo": "Mesas de regalos",
        "ayuda": "Opcional. Tienda y número de evento o link.",
        "campos": [("nombre", "Tienda", "Liverpool", 60), ("codigo", "Número de evento", "51384920", 40),
                   ("url", "Link", "https://…", 300)],
        "obligatorio": "nombre",
        "maximo": 5,
        "agregar": "Agregar otra mesa",
    },
}

# Datos propios de algunos diseños (las claves que lee cada plantilla).
EXTRAS_DEL_DISENO = {
    "xv-gira-03": ["ciudad"],
    "fiesta-consola-03": ["nivel"],
    "fiesta-loteria-02": ["carta_numero", "carta_titulo", "carta_dibujo"],
    "baby-shower-lunas-01": ["paleta"],
}

# Tabla de pañales por inicial del apellido (la misma del demo); se ajusta después si piden otra.
PANALES_POR_DEFECTO = [
    {"desde": "A", "hasta": "F", "talla": "Etapa 1"},
    {"desde": "G", "hasta": "L", "talla": "Etapa 2"},
    {"desde": "M", "hasta": "R", "talla": "Etapa 3"},
    {"desde": "S", "hasta": "Z", "talla": "Etapa 4"},
]


def votacion_por_defecto():
    return {
        "pregunta": "¿Niña o niño?",
        "subtitulo": "Haz tu predicción: el gran secreto se revela el día del baby shower.",
        "opciones": [
            {"clave": "nina", "texto": "Niña", "color": "#E7A3B7", "revelacion": "¡Es niña!"},
            {"clave": "nino", "texto": "Niño", "color": "#8FB8E3", "revelacion": "¡Es niño!"},
        ],
        "resultado": "",
    }


# ------------------------------------------------------------------
# El formulario
# ------------------------------------------------------------------
def _texto(etiqueta, ejemplo="", requerido=False, largo=200, ayuda="", area=False):
    widget = forms.Textarea(attrs={"rows": 3}) if area else forms.TextInput()
    widget.attrs["placeholder"] = ejemplo
    return forms.CharField(label=etiqueta, required=requerido, max_length=largo, help_text=ayuda, widget=widget)


def _link(etiqueta, ayuda="Copia el link de Google Maps (botón Compartir)."):
    return forms.URLField(label=etiqueta, required=False, max_length=500, help_text=ayuda, assume_scheme="https",
                          widget=forms.URLInput(attrs={"placeholder": "https://maps.app.goo.gl/…", "inputmode": "url"}))


def _fecha(etiqueta, requerido=False, ayuda=""):
    return forms.DateField(label=etiqueta, required=requerido, help_text=ayuda,
                           widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))


class FormularioPedido(forms.Form):
    def __init__(self, *args, pedido, **kwargs):
        super().__init__(*args, **kwargs)
        self.pedido = pedido
        plantilla = pedido.plantilla
        tipo = plantilla.tipo_evento
        self.tipo = tipo
        self.con_rsvp = pedido.nivel != "imagen" and plantilla.soporta_rsvp
        self.con_musica = pedido.nivel == "premium" and plantilla.soporta_musica
        self.con_galeria = pedido.nivel != "imagen" and plantilla.soporta_galeria
        self.con_votacion = pedido.nivel == "premium" and plantilla.soporta_votacion
        self.dos_lugares = tipo in ("boda", "xv")
        f = self.fields
        secciones = []

        # --- Lo básico ---
        etiqueta, ejemplo = ANFITRIONES.get(tipo, ANFITRIONES["evento"])
        f["anfitriones"] = _texto(etiqueta, ejemplo, requerido=True, largo=120,
                                  ayuda="Tal cual quieren que aparezca, en grande.")
        f["titulo"] = _texto("Título del evento", TITULO_AUTOMATICO.get(tipo, "{}").format("…"), largo=150,
                             ayuda="Opcional. Si lo dejas vacío lo armamos con los nombres.")
        f["fecha"] = _fecha("Fecha del evento", requerido=True)
        f["hora"] = forms.TimeField(label="Hora", widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
        f["mensaje"] = _texto("Mensaje para tus invitados", MENSAJE_EJEMPLO.get(tipo, ""), largo=600, area=True)
        secciones.append(("Lo básico", "", ["anfitriones", "titulo", "fecha", "hora", "mensaje"], []))

        if tipo == "baby_shower":
            f["fecha_probable_parto"] = _fecha("Fecha probable de parto",
                                               ayuda="Con ella la invitación cuenta las semanas del embarazo.")
            f["bebe_nombre"] = _texto("Nombre del bebé", "Ej. Emilia", largo=60,
                                      ayuda="Opcional. Déjalo vacío si será sorpresa.")
            campos = ["fecha_probable_parto", "bebe_nombre"]
            if self.con_votacion:
                f["votacion"] = forms.BooleanField(
                    label="Juego en vivo «¿Niña o niño?»", required=False,
                    help_text="Tus invitados votan y el día del evento revelamos el resultado.")
                campos.append("votacion")
            secciones.append(("El bebé", "", campos, []))

        if tipo == "graduacion":
            f["carrera"] = _texto("Carrera o nivel", "Ej. Licenciatura en Arquitectura", largo=120)
            f["institucion"] = _texto("Escuela", "Ej. Universidad Autónoma de Nuevo León", largo=120)
            f["generacion"] = _texto("Generación", "Ej. 2022 — 2026", largo=40)
            secciones.append(("La graduación", "", ["carrera", "institucion", "generacion"], []))

        # --- Dónde ---
        if self.dos_lugares:
            f["ceremonia_etiqueta"] = _texto("Tipo de ceremonia", "Ej. Ceremonia religiosa, Misa, Civil", largo=60,
                                             ayuda="Opcional. Si no, dirá «Ceremonia».")
            f["ceremonia_nombre"] = _texto("Lugar de la ceremonia", "Ej. Parroquia de San Pedro, Tlaquepaque", largo=200)
            f["ceremonia_mapa"] = _link("Ubicación de la ceremonia")
            f["recepcion_nombre"] = _texto("Lugar de la recepción", "Ej. Jardín Casa Terracota", largo=200)
            f["recepcion_mapa"] = _link("Ubicación de la recepción")
            campos = ["ceremonia_etiqueta", "ceremonia_nombre", "ceremonia_mapa", "recepcion_nombre", "recepcion_mapa"]
            ayuda = "Si solo hay un lugar, llena únicamente el de la recepción."
        else:
            f["lugar_nombre"] = _texto("Lugar", "Ej. Salón Los Arcos", requerido=True, largo=200)
            f["lugar_direccion"] = _texto("Dirección", "Ej. Av. Francisco Sosa 215, Coyoacán", largo=200,
                                          ayuda="Opcional.")
            f["lugar_mapa"] = _link("Ubicación")
            campos = ["lugar_nombre", "lugar_direccion", "lugar_mapa"]
            ayuda = ""
        secciones.append(("Dónde", ayuda, campos, []))

        # --- Detalles ---
        f["dresscode"] = _texto("Código de vestimenta", "Ej. Formal, tonos tierra bienvenidos", largo=120,
                                ayuda="Opcional.")
        f["usar_color"] = forms.BooleanField(label="Quiero sugerir un color", required=False)
        f["color"] = forms.CharField(label="Color", required=False, initial="#C0694A",
                                     widget=forms.TextInput(attrs={"type": "color"}))
        f["admite_ninos"] = forms.ChoiceField(
            label="¿Los niños están invitados?", required=False, initial="",
            choices=[("", "No mencionarlo"), ("si", "Sí, niños bienvenidos"), ("no", "Solo adultos")],
            widget=forms.RadioSelect)
        campos = ["dresscode", "usar_color", "color", "admite_ninos"]
        if self.con_rsvp:
            f["fecha_limite_rsvp"] = _fecha("Fecha límite para confirmar", ayuda="Opcional.")
            campos.append("fecha_limite_rsvp")
        secciones.append(("Detalles", "", campos, []))

        # --- Programa y familia ---
        repetibles = ["itinerario"]
        campos = []
        if tipo in ("xv", "graduacion"):
            f["padres"] = _texto("Mis papás", "Ej. Laura Méndez & Ricardo Torres", largo=150, ayuda="Opcional.")
            campos.append("padres")
        if tipo in ("boda", "xv", "graduacion"):
            repetibles.append("padrinos")
        secciones.append(("Programa y familia", "", campos, repetibles))

        # --- Regalos ---
        if tipo == "baby_shower":
            f["lluvia_sobres"] = _texto("Lluvia de sobres", "Ej. El día del evento habrá una cajita para sobres.",
                                        largo=200, ayuda="Opcional.")
            f["lluvia_panales"] = forms.BooleanField(
                label="Lluvia de pañales", required=False,
                help_text="Cada invitado ve qué talla le toca según la inicial de su apellido.")
            secciones.append(("Regalos", "", ["lluvia_sobres", "lluvia_panales"], ["mesas_regalos"]))
        else:
            f["mesa_regalos_url"] = forms.URLField(
                label="Link de la mesa de regalos", required=False, max_length=500, assume_scheme="https",
                help_text="Opcional.", widget=forms.URLInput(attrs={"placeholder": "https://mesaderegalos.liverpool.com.mx/…"}))
            secciones.append(("Regalos", "", ["mesa_regalos_url"], []))

        # --- Del diseño ---
        extras = EXTRAS_DEL_DISENO.get(plantilla.slug_tema, [])
        if "ciudad" in extras:
            f["ciudad"] = _texto("Ciudad", "Ej. Guadalajara, Jal.", largo=60, ayuda="Sale en el boleto de la gira.")
        if "nivel" in extras:
            f["nivel"] = _texto("¿Cuántos años cumple?", "Ej. 30", largo=3, ayuda="Sale como «Nivel 30 desbloqueado».")
        if "carta_numero" in extras:
            f["carta_numero"] = _texto("Número de la carta", "Ej. 80 (los años que cumple)", largo=3)
            f["carta_titulo"] = _texto("Nombre de la carta", "Ej. La Cumpleañera", largo=30)
            f["carta_dibujo"] = forms.ChoiceField(label="Dibujo de la carta", required=False,
                                                  choices=[("pastel", "Pastel"), ("pinata", "Piñata")])
        if "paleta" in extras:
            f["paleta"] = forms.ChoiceField(label="Colores", required=False, choices=[
                ("", "Lavanda (neutro)"), ("rosa", "Rosa"), ("azul", "Azul")])
        if extras:
            secciones.append(("Detalles del diseño", "", [n for n in extras if n in f], []))

        # --- Música y fotos (las fotos se leen aparte, de request.FILES) ---
        if self.con_musica:
            f["cancion"] = _texto("Tu canción", "Nombre y artista, o link de YouTube o Spotify", largo=300)
            secciones.append(("Música y fotos" if self.con_galeria else "Música", "", ["cancion"], []))
        elif self.con_galeria:
            secciones.append(("Fotos", "", [], []))

        f["notas"] = _texto("¿Algo más que debamos saber?", "Ej. Queremos que diga «Nos casamos» en vez de…",
                            largo=1500, area=True)
        secciones.append(("Algo más", "", ["notas"], []))
        self._secciones = secciones

        for campo in f.values():
            if campo.required:
                campo.widget.attrs["required"] = True

    def secciones(self, filas):
        """Secciones listas para pintar: campos con su BoundField y filas repetibles."""
        salida = []
        for titulo, ayuda, nombres, repetibles in self._secciones:
            salida.append({
                "titulo": titulo,
                "ayuda": ayuda,
                "campos": [self[n] for n in nombres],
                "repetibles": [self._repetible(r, filas.get(r) or [{}]) for r in repetibles],
                "fotos": titulo in ("Música y fotos", "Fotos"),
            })
        return salida

    @staticmethod
    def _repetible(clave, filas):
        spec = REPETIBLES[clave]
        return {
            "clave": clave, **spec,
            "filas": [
                [{"nombre": f"{clave}-{c}", "etiqueta": e, "ejemplo": ej, "largo": lg, "valor": fila.get(c, "")}
                 for c, e, ej, lg in spec["campos"]]
                for fila in filas
            ],
            "molde": [{"nombre": f"{clave}-{c}", "etiqueta": e, "ejemplo": ej, "largo": lg, "valor": ""}
                      for c, e, ej, lg in spec["campos"]],
        }

    def repetibles(self):
        return [r for *_, repetibles in self._secciones for r in repetibles]

    def clean(self):
        datos = super().clean()
        if self.dos_lugares and not (datos.get("ceremonia_nombre") or datos.get("recepcion_nombre")):
            self.add_error("recepcion_nombre", "Escribe al menos un lugar (ceremonia o recepción).")
        if datos.get("ceremonia_mapa") and not datos.get("ceremonia_nombre"):
            self.add_error("ceremonia_nombre", "¿Cómo se llama el lugar de esta ubicación?")
        if datos.get("recepcion_mapa") and not datos.get("recepcion_nombre"):
            self.add_error("recepcion_nombre", "¿Cómo se llama el lugar de esta ubicación?")
        color = datos.get("color") or ""
        if datos.get("usar_color") and not (len(color) == 7 and color.startswith("#")):
            self.add_error("color", "Elige un color.")
        return datos


# ------------------------------------------------------------------
# Filas repetibles
# ------------------------------------------------------------------
def leer_filas(post, grupos):
    """
    Lee las filas del POST y las valida. Regresa (filas, errores):
    filas = {"itinerario": [{"hora": "7:00 PM", "evento": "Cena"}, …]}.
    Los renglones totalmente vacíos se ignoran (el cliente dejó uno de más).
    """
    filas, errores = {}, []
    validar_url = URLValidator(schemes=["http", "https"])
    for grupo in grupos:
        spec = REPETIBLES[grupo]
        columnas = {clave: post.getlist(f"{grupo}-{clave}") for clave, *_ in spec["campos"]}
        total = max((len(v) for v in columnas.values()), default=0)
        lista = []
        for i in range(total):
            fila = {clave: (valores[i] if i < len(valores) else "").strip() for clave, valores in columnas.items()}
            if not any(fila.values()):
                continue
            for clave, etiqueta, _, largo in spec["campos"]:
                fila[clave] = fila[clave][:largo]
            if not fila[spec["obligatorio"]]:
                etiqueta = next(e for c, e, *_ in spec["campos"] if c == spec["obligatorio"])
                errores.append(f"{spec['titulo']}: a un renglón le falta «{etiqueta}».")
            if fila.get("url"):
                if "://" not in fila["url"]:
                    fila["url"] = "https://" + fila["url"]
                try:
                    validar_url(fila["url"])
                except ValidationError:
                    errores.append(f"{spec['titulo']}: el link «{fila['url']}» no parece válido.")
            lista.append(fila)
        if len(lista) > spec["maximo"]:
            errores.append(f"{spec['titulo']}: máximo {spec['maximo']} renglones.")
        filas[grupo] = lista
    return filas, errores


# ------------------------------------------------------------------
# Fotos
# ------------------------------------------------------------------
def preparar_foto(archivo):
    """
    Revisa que sea una foto de verdad y la deja lista para la galería:
    derecha (los celulares la guardan "acostada" con una etiqueta EXIF),
    máximo 2000 px por lado y en JPEG. Al volver a guardarla se quitan los
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
            imagen.thumbnail((LADO_MAXIMO_FOTO, LADO_MAXIMO_FOTO), Image.LANCZOS)
            salida = BytesIO()
            imagen.save(salida, "JPEG", quality=85, optimize=True, progressive=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError(f"«{archivo.name}» no se pudo abrir. Usa fotos JPG o PNG.")
    return ContentFile(salida.getvalue(), name=f"{uuid.uuid4().hex[:12]}.jpg")


# ------------------------------------------------------------------
# De la invitación al formulario (para corregir) y de regreso
# ------------------------------------------------------------------
CLAVES_DEL_FORMULARIO = [
    # claves de contenido_extra que el formulario controla por completo; las
    # demás (ej. frase_superior o el resultado de la votación) no se tocan
    "lugar_ceremonia_etiqueta", "lugar_ceremonia_nombre", "lugar_ceremonia_mapa_url",
    "lugar_recepcion_nombre", "lugar_recepcion_mapa_url", "lugar_direccion",
    "dresscode", "dresscode_color", "admite_ninos", "padres", "padrinos", "itinerario",
    "mesa_regalos_url", "mesas_regalos", "lluvia_sobres", "lluvia_panales",
    "fecha_probable_parto", "bebe_nombre", "carrera", "institucion", "generacion",
    "ciudad", "nivel", "carta_numero", "carta_titulo", "carta_dibujo", "paleta",
]


def datos_iniciales(pedido):
    """Lo ya capturado, para que el cliente vea sus datos al volver a abrir el link."""
    inv = pedido.invitacion
    if inv is None:
        return {}, {}
    extra = inv.contenido_extra or {}
    local = timezone.localtime(inv.fecha_evento)
    titulo_auto = TITULO_AUTOMATICO.get(pedido.plantilla.tipo_evento, "{}").format(inv.anfitriones)
    iniciales = {
        "anfitriones": inv.anfitriones,
        "titulo": "" if inv.titulo_evento == titulo_auto else inv.titulo_evento,
        "fecha": local.date(),
        "hora": local.time().replace(second=0, microsecond=0),
        "mensaje": inv.mensaje_bienvenida,
        "lugar_nombre": inv.lugar_nombre,
        "lugar_mapa": inv.lugar_mapa_url,
        "fecha_limite_rsvp": inv.fecha_limite_rsvp,
        "ceremonia_etiqueta": extra.get("lugar_ceremonia_etiqueta", ""),
        "ceremonia_nombre": extra.get("lugar_ceremonia_nombre", ""),
        "ceremonia_mapa": extra.get("lugar_ceremonia_mapa_url", ""),
        "recepcion_nombre": extra.get("lugar_recepcion_nombre", ""),
        "recepcion_mapa": extra.get("lugar_recepcion_mapa_url", ""),
        "usar_color": bool(extra.get("dresscode_color")),
        "color": extra.get("dresscode_color") or "#C0694A",
        "admite_ninos": {True: "si", False: "no"}.get(extra.get("admite_ninos"), ""),
        "votacion": bool(extra.get("votacion")),
        "lluvia_panales": bool(extra.get("lluvia_panales")),
        "cancion": pedido.cancion,
        "notas": pedido.notas,
    }
    for clave in ("lugar_direccion", "dresscode", "padres", "mesa_regalos_url", "lluvia_sobres", "bebe_nombre",
                  "fecha_probable_parto", "carrera", "institucion", "generacion", "ciudad", "nivel",
                  "carta_numero", "carta_titulo", "carta_dibujo", "paleta"):
        if extra.get(clave):
            iniciales[clave] = extra[clave]
    filas = {grupo: extra.get(grupo) or [] for grupo in REPETIBLES}
    return iniciales, filas


def guardar_pedido(pedido, datos, filas, fotos, borrar_fotos=()):
    """
    Crea o actualiza la invitación del pedido con lo que mandó el cliente.
    Siempre queda como borrador (activa=False): tú la revisas y la publicas.
    """
    tipo = pedido.plantilla.tipo_evento
    inv = pedido.invitacion or Invitacion(plantilla=pedido.plantilla, nivel=pedido.nivel, activa=False)
    anfitriones = datos["anfitriones"].strip()
    inv.anfitriones = anfitriones
    inv.titulo_evento = datos.get("titulo") or TITULO_AUTOMATICO.get(tipo, "{}").format(anfitriones)
    inv.fecha_evento = timezone.make_aware(datetime.combine(datos["fecha"], datos["hora"]))
    inv.mensaje_bienvenida = datos.get("mensaje", "")
    inv.fecha_limite_rsvp = datos.get("fecha_limite_rsvp")
    inv.lugar_nombre = datos.get("lugar_nombre", "")
    inv.lugar_mapa_url = datos.get("lugar_mapa", "")

    extra = {k: v for k, v in (inv.contenido_extra or {}).items() if k not in CLAVES_DEL_FORMULARIO}
    votacion_anterior = extra.pop("votacion", None)
    nuevo = {
        "lugar_ceremonia_etiqueta": datos.get("ceremonia_etiqueta"),
        "lugar_ceremonia_nombre": datos.get("ceremonia_nombre"),
        "lugar_ceremonia_mapa_url": datos.get("ceremonia_mapa"),
        "lugar_recepcion_nombre": datos.get("recepcion_nombre"),
        "lugar_recepcion_mapa_url": datos.get("recepcion_mapa"),
        "lugar_direccion": datos.get("lugar_direccion"),
        "dresscode": datos.get("dresscode"),
        "dresscode_color": datos.get("color") if datos.get("usar_color") else None,
        "padres": datos.get("padres"),
        "mesa_regalos_url": datos.get("mesa_regalos_url"),
        "lluvia_sobres": datos.get("lluvia_sobres"),
        "lluvia_panales": PANALES_POR_DEFECTO if datos.get("lluvia_panales") else None,
        "fecha_probable_parto": datos["fecha_probable_parto"].isoformat() if datos.get("fecha_probable_parto") else None,
        "bebe_nombre": datos.get("bebe_nombre"),
        "carrera": datos.get("carrera"),
        "institucion": datos.get("institucion"),
        "generacion": datos.get("generacion"),
        "ciudad": datos.get("ciudad"),
        "nivel": datos.get("nivel"),
        "carta_numero": datos.get("carta_numero"),
        "carta_titulo": datos.get("carta_titulo"),
        "carta_dibujo": datos.get("carta_dibujo"),
        "paleta": datos.get("paleta"),
        **filas,
    }
    extra.update({k: v for k, v in nuevo.items() if v})    # vacío = la plantilla no muestra esa parte
    if datos.get("admite_ninos") in ("si", "no"):
        extra["admite_ninos"] = datos["admite_ninos"] == "si"
    if datos.get("votacion"):
        # si ya existía se conserva tal cual (con el resultado, si ya se reveló)
        extra["votacion"] = votacion_anterior or votacion_por_defecto()
    inv.contenido_extra = extra

    with transaction.atomic():
        inv.save()
        for foto in inv.galeria.filter(pk__in=borrar_fotos):
            foto.imagen.delete(save=False)      # Django no borra el archivo solo
            foto.delete()
        siguiente = (inv.galeria.order_by("-orden").values_list("orden", flat=True).first() or 0) + 1
        for i, foto in enumerate(fotos):
            ImagenGaleria.objects.create(invitacion=inv, imagen=foto, orden=siguiente + i)
        pedido.invitacion = inv
        pedido.cancion = datos.get("cancion", "")
        pedido.notas = datos.get("notas", "")
        pedido.enviado_en = timezone.now()
        pedido.save()
    return inv
