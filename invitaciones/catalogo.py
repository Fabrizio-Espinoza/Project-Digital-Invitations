"""
El catálogo de diseños que se muestra en la página principal (/).

Es una lista escrita a mano, no una consulta a Plantilla, a propósito:
aquí van los textos de VENTA (la frase, para quién es ideal), que no son
datos del motor. Cada diseño apunta a su invitación demo (creada con
crear_todos_los_demos) y a su captura en
static/invitaciones/catalogo/<slug_tema>.webp (python manage.py capturar_catalogo).

Plantilla nueva → agregarla aquí, a DEMOS de crear_todos_los_demos y
correr capturar_catalogo. Las pruebas avisan si falta alguna de las tres.
"""

TIPOS = [
    # (clave, título de la sección, cómo se lee en el mensaje de WhatsApp: "para ...")
    ("boda", "Bodas", "mi boda"),
    ("xv", "XV años", "unos XV años"),
    ("graduacion", "Graduaciones", "una graduación"),
    ("fiesta", "Fiestas y cumpleaños", "una fiesta"),
    ("baby_shower", "Baby showers", "un baby shower"),
]

DISENOS = [
    # ----- Bodas -----
    {
        "tipo": "boda",
        "nombre": "Terracota Velada",
        "slug_tema": "boda-minimal-01",
        "demo": "demo-boda-daniela-andres",
        "frase": "Marco de rosas, letra manuscrita y tonos tierra. Romántica y cálida.",
        "ideal": "Bodas de jardín, hacienda o religiosas",
    },
    {
        "tipo": "boda",
        "nombre": "Cobalto Editorial",
        "slug_tema": "boda-editorial-02",
        "demo": "demo-cobalto-editorial",
        "frase": "Tu boda como portada de revista de moda: tipográfica y en azul cobalto.",
        "ideal": "Parejas modernas y bodas en la ciudad",
    },
    {
        "tipo": "boda",
        "nombre": "Hotel Amor",
        "slug_tema": "boda-hotel-03",
        "demo": "demo-hotel-amor",
        "frase": "Un hotel boutique con su monograma: cada invitado hace check-in y recibe su llave.",
        "ideal": "Bodas en hotel, hacienda o de destino",
    },
    # ----- XV años -----
    {
        "tipo": "xv",
        "nombre": "Medianoche Dorada",
        "slug_tema": "xv-medianoche-01",
        "demo": "demo-xv-valentina",
        "frase": "Cielo de estrellas, arco dorado y tiara. Clásica y de gala.",
        "ideal": "XV de noche, vals y vestido de princesa",
    },
    {
        "tipo": "xv",
        "nombre": "Carnet de Baile",
        "slug_tema": "xv-carnet-02",
        "demo": "demo-xv-regina",
        "frase": "Llega envuelta como regalo: al desatar el moño empieza la música.",
        "ideal": "Quinceañeras coquette: moños, perlas y rosa",
    },
    {
        "tipo": "xv",
        "nombre": "La Gira",
        "slug_tema": "xv-gira-03",
        "demo": "demo-xv-ximena",
        "frase": "Ella es la estrella pop: boleto de concierto, photocards y pulsera de la amistad.",
        "ideal": "Quinceañeras fans de los conciertos",
    },
    # ----- Graduaciones -----
    {
        "tipo": "graduacion",
        "nombre": "Laurel de Oro",
        "slug_tema": "graduacion-editorial-01",
        "demo": "demo-graduacion-valeria-montes",
        "frase": "Azul medianoche, laurel y oro como un título universitario.",
        "ideal": "Graduaciones formales de universidad",
    },
    {
        "tipo": "graduacion",
        "nombre": "Tarea Cumplida",
        "slug_tema": "graduacion-cuaderno-02",
        "demo": "demo-graduacion-diego",
        "frase": "La última hoja del cuaderno: marcatextos, un 10 en pluma roja y pase de lista.",
        "ideal": "Prepa, secundaria o graduaciones con humor",
    },
    {
        "tipo": "graduacion",
        "nombre": "Próxima Salida",
        "slug_tema": "graduacion-salida-03",
        "demo": "demo-graduacion-camila",
        "frase": "Graduarse es despegar: tablero de aeropuerto que gira y pase de abordar.",
        "ideal": "Cualquier graduación que abre una etapa nueva",
    },
    # ----- Fiestas -----
    {
        "tipo": "fiesta",
        "nombre": "Noche Neón",
        "slug_tema": "fiesta-neon-01",
        "demo": "demo-fiesta-sofia",
        "frase": "Flyer de antro con bola disco, luces y boleto de entrada.",
        "ideal": "Cumpleaños de noche y fiestas de adultos",
    },
    {
        "tipo": "fiesta",
        "nombre": "La Lotería",
        "slug_tema": "fiesta-loteria-02",
        "demo": "demo-loteria-lupita",
        "frase": "Cartas de lotería y papel picado. Al confirmar, ¡Lotería!",
        "ideal": "Cumpleaños familiares, posadas y fiestas patrias",
    },
    {
        "tipo": "fiesta",
        "nombre": "Nivel Desbloqueado",
        "slug_tema": "fiesta-consola-03",
        "demo": "demo-fiesta-rodrigo",
        "frase": "El celular se vuelve consola retro, con botones que sí funcionan.",
        "ideal": "Cumpleaños gamers de cualquier edad",
    },
    # ----- Baby showers -----
    {
        "tipo": "baby_shower",
        "nombre": "Diez Lunas",
        "slug_tema": "baby-shower-lunas-01",
        "demo": "demo-baby-mariana-diego",
        "frase": "Diez lunas que se llenan con el embarazo y votación en vivo: ¿niña o niño?",
        "ideal": "Baby showers y revelaciones de género",
    },
    {
        "tipo": "baby_shower",
        "nombre": "Entrega Especial",
        "slug_tema": "baby-shower-entrega-02",
        "demo": "demo-baby-entrega",
        "frase": "El bebé viene en camino como paquete: guía de envío, rastreo y sello de ¡Recibido!",
        "ideal": "Papás con humor, neutral en género",
    },
    {
        "tipo": "baby_shower",
        "nombre": "Pancito en el Horno",
        "slug_tema": "baby-shower-panaderia-03",
        "demo": "demo-baby-pancito",
        "frase": "Hay un pancito en el horno: conchas, receta de la abuela y votación por sabor.",
        "ideal": "Baby showers cálidos y muy mexicanos",
    },
]


def captura(diseno):
    """Ruta (para {% static %}) de la captura del diseño."""
    return f"invitaciones/catalogo/{diseno['slug_tema']}.webp"
