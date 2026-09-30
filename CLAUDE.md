Resumen técnico — Motor de Invitaciones Digitales
24 sep 2026 · @Fabrizio Espinoza Hurtado
1. Contexto del negocio
Negocio nuevo (separado de Nexus Producciones) de invitaciones digitales interactivas para bodas, XV años, graduaciones, eventos y fiestas, vendidas por Meta Ads en el mercado mexicano.
Producto: el diferenciador frente a la competencia (ej. "Digital RSVP", $295 MXN) es lo interactivo — countdown en vivo, RSVP en tiempo real, música de fondo, galería de fotos — aunque también se atienden pedidos de solo imagen/PDF.
Roadmap de fases:
• Fase 0 — marca y WhatsApp separados de Nexus
• Fase 1 — producto: motor Django + 1-2 plantillas pulidas + PWA (fase actual)
• Fase 2 — precios en 3 niveles, por encima de $295 MXN
• Fase 3 — Meta Ads con creativo tipo screen-recording del RSVP en vivo
• Fase 4 — venta por WhatsApp, calcada del flujo que ya usa en Nexus
Dentro de Fase 1 se avanzó: el motor completo, la primera plantilla de boda ("Terracota Velada") con diseño real terminado, y quedó pendiente la PWA y la segunda plantilla.
2. Arquitectura del motor
Stack: Django (backend, templates, admin), SQLite en desarrollo, sin frontend framework — HTML + CSS + JavaScript vanilla (sin librerías de animación externas).
Modelos de datos (app invitaciones)
• Plantilla — define un DISEÑO reutilizable (tipo_evento, slug_tema, y flags soporta_rsvp/soporta_musica/soporta_galeria). No guarda datos de un cliente específico.
• Invitacion — el evento de un cliente: slug único (URL pública), UUID interno estable, FK a Plantilla, nivel (imagen / interactiva / premium), datos comunes (título, anfitriones, fecha, mensaje), y contenido_extra (JSONField) para todo lo que varía según el tipo de evento (vestimenta, ceremonia/recepción, itinerario, mesa de regalos, admite_niños) sin necesitar migraciones nuevas por cada dato opcional.
• ImagenGaleria — FK a Invitacion, un registro por foto (permite reordenar/subir desde el admin).
• Confirmacion — un registro por respuesta de RSVP (nombre, asistencia, acompañantes, mensaje).
Patrón "motor + plantillas"
• base_interactiva.html es el motor: contiene TODA la estructura HTML, la lógica JS (countdown, RSVP por fetch, animaciones de scroll) y los {% block %} de Django para decoración y estilos. Se escribe una sola vez.
• Cada plantilla visual (ej. boda-minimal-01.html) hace {% extends %} del motor y solo sobreescribe bloques de estilos ({% block estilos %}) y decoración ({% block decoracion_superior %}, decoracion_info, decoracion_inferior) — nunca reescribe el RSVP ni el countdown.
• Bloques opcionales extra del motor: {% block theme_color %} (color de la barra del navegador; por defecto plantilla.color_tema) y {% block scripts_tema %} (JS decorativo del tema, corre después del motor; si falla, la invitación funciona igual).
• La vista (views.py) arma el nombre del template dinámicamente a partir de plantilla.slug_tema (invitaciones/temas/{slug_tema}.html), así cada diseño nuevo es literalmente un archivo distinto, sin if/else gigantes en un solo template.
• Flags combinadas en la vista (mostrar_rsvp, mostrar_musica, mostrar_galeria) cruzan el nivel pagado por el cliente con lo que la Plantilla soporta, para que un cliente de paquete básico nunca vea features que no pagó.
Estructura visual final (scroll-snap por pantallas)
La invitación se divide en "pantallas" que ocupan 100dvh cada una, enganchadas con CSS scroll-snap:
1. Hero (marco floral + nombres)
2. Info (Día/Hora, Ceremonia/Recepción, Vestimenta, Countdown, botones de acción)
3. Extra (Itinerario, Mesa de regalos, nota de niños) — solo si hay contenido
4. Galería — solo si hay fotos
5. RSVP (con fecha límite si aplica)
3. Decisiones de arquitectura y por qué
Decisión
Razón
contenido_extra como JSONField en vez de columnas fijas
Una boda necesita "padrinos"/"mesa de regalos"; unos XV necesitan "chambelanes"/"vals". Meter esto en columnas haría crecer el modelo sin control con cada tipo de evento nuevo.
ImagenGaleria como modelo aparte (no lista JSON)
Permite reordenar/subir fotos desde el admin sin tocar código, y usa ImageField para manejar el archivo real, no solo una URL.
Nombre del template armado desde slug_tema
Cada diseño nuevo es un archivo .html distinto — evita un solo template gigante lleno de condicionales por tipo de evento.
Motor (base_interactiva.html) separado de plantillas visuales
Un bug o mejora en la lógica (RSVP, countdown, animaciones) se arregla UNA vez y lo heredan todas las plantillas presentes y futuras automáticamente vía {% extends %}.
position: relative + position: absolute para superponer capas (marco floral detrás del texto)
Único mecanismo de CSS para que dos elementos ocupen el mismo espacio visual; se repitió para el hero y para la pantalla de info.
position: fixed para el botón de música
Necesita quedar visible en la misma esquina de pantalla sin importar el scroll, a diferencia de absolute que depende de su contenedor padre.
Botones de asistencia (radio oculto + <label> estilizado) en vez de <select> nativo
Un <select> no se puede diseñar directamente en CSS; el patrón input-oculto + label + selector :checked + label es el estándar para cualquier control de opción único visualmente personalizado.
Música con botón manual en vez de solo autoplay
Los navegadores (especialmente en móvil) bloquean el autoplay de audio con sonido por política de seguridad — se requiere una interacción real del usuario.
scroll-snap-align sin scroll-snap-stop: always
always bloqueaba los saltos programáticos de ancla (el botón "Confirmar" no llegaba al RSVP) — se sacrificó el enganche forzado en scroll rápido a cambio de que los botones internos funcionaran.
Interceptar clics en <a href="#..."> con JS (apagar/prender scroll-snap-type)
Bug conocido de iOS Safari: un salto de ancla con scroll-snap activo puede "rebotar" de vuelta a la sección anterior. Apagar el snap durante el scrollIntoView y reactivarlo después lo evita.
Polling cada 8s para el conteo de RSVP en vez de WebSockets/Django Channels
Suficiente para MVP, mucho más simple de desplegar; el único punto que cambiaría si el negocio necesita algo instantáneo de verdad.
@ensure_csrf_cookie en la vista de detalle
Sin esto, el token CSRF nunca se generaba porque el template no usa {% csrf_token %} — el fetch del RSVP fallaba con 403 por header vacío.
4. Problemas técnicos resueltos
Síntoma
Causa raíz
Solución
TemplateDoesNotExist
Archivos (models.py, templates, imágenes) guardados en la raíz del proyecto o con mayúsculas (Models.py) en vez de en la carpeta/ruta exacta que Django espera.
Mover cada archivo a su ruta correcta; Python es sensible a mayúsculas en imports aunque Windows no lo sea en el explorador.
RuntimeError: doesn't declare an explicit app_label
'invitaciones' nunca se guardó en INSTALLED_APPS (el Ctrl+S no se aplicó).
Insertar la línea directo con sed desde terminal, confirmarlo con grep.
RSVP devolvía 403 Forbidden
La cookie csrftoken nunca se generaba porque el template no usa {% csrf_token %}.
Decorar la vista con @ensure_csrf_cookie y mandar la cookie en el header X-CSRFToken desde JS.
Cambios de CSS "no se aplicaban"
El archivo tenía el bloque de RSVP duplicado: una versión vieja más abajo ganaba por la cascada de CSS.
Eliminar el bloque duplicado completo.
Botón/título perdían su estilo de golpe
Al borrar el duplicado se llevó de encuentro reglas que sí se usaban (.rsvp h2, #form-rsvp button).
Reconstruir el archivo completo, limpio y organizado por secciones.
TemplateDoesNotExist: base_interactiva.html
El {% extends %} apuntaba a la ruta sin la carpeta temas/.
Corregir la ruta relativa.
Prettier rompió los templates
No entiende {% %} de Django, aplastó etiquetas en una sola línea.
Desactivar "Format on Save" en .html de Django; usarlo solo en .py.
Fecha en inglés
LANGUAGE_CODE = 'en-us' (default de Django).
Cambiar a 'es-mx' en settings.py.
Marco floral duplicado / no llegaba a las esquinas
La imagen (ya trae las 4 esquinas) se repetía en dos bloques fluyendo normal en la página, no de fondo.
position: absolute para la imagen + position: relative/z-index:1 para el contenido, superpuestos.
Página en blanco entre secciones (scroll-snap)
Secciones min-height:100vh sin contenido (galería sin fotos) se mostraban vacías.
{% if mostrar_galeria and invitacion.galeria.all %}.
Botón "Confirmar" no saltaba al RSVP en celular
scroll-snap-stop: always bloqueaba saltos directos de ancla.
Quitar scroll-snap-stop: always.
El salto "rebotaba" de vuelta (solo iPhone/Safari)
Bug conocido de iOS con scroll-snap + salto de ancla.
JS: apagar scroll-snap-type antes del scrollIntoView, reactivar ~1s después.
No conectaba desde el iPhone
Servidor en 127.0.0.1, ALLOWED_HOSTS vacío, Firewall bloqueando el puerto.
runserver 0.0.0.0:8000, ALLOWED_HOSTS=['*'] en dev, regla de Firewall para el puerto 8000.
musica_url no aceptaba ruta local
URLField exige URL absoluta con esquema.
Usar http://<ip>:8000/static/... completa.
Música no sonaba sola
Navegadores bloquean autoplay de audio con sonido, sobre todo en móvil.
Botón flotante (position: fixed) que el usuario toca para reproducir/pausar.
Botón de música a veces no pausaba
El listener del botón se registraba dentro de actualizarCountdown(), que corre cada segundo (un listener nuevo por segundo).
Sacar el bloque de música fuera del countdown para registrarlo una sola vez.
Countdown 6 horas antes de la hora real
TIME_ZONE = 'UTC': la hora capturada en el admin se tomaba como UTC.
TIME_ZONE = 'America/Mexico_City' (revisar la hora de invitaciones capturadas antes del cambio).
Fotos de galería con 404 / guardadas en la raíz
No existían MEDIA_URL ni MEDIA_ROOT.
MEDIA_ROOT = BASE_DIR / 'media' + static() en urls.py cuando DEBUG.
Títulos en Bodoni Moda se leían mal ("Mateo" → "Matco")
El eje de tamaño óptico (opsz) en automático adelgaza los trazos finos a tamaños grandes y la barra de la "e" desaparece.
Fijar opsz ≈ 30-40 % del tamaño real en pantalla (24 en nombres, 18 en títulos).
5. Convenciones acordadas
Estructura de carpetas
• Templates: invitaciones/templates/invitaciones/temas/<slug_tema>.html (una plantilla visual = un archivo).
• Static: invitaciones/static/invitaciones/img/ para imágenes, invitaciones/static/invitaciones/musica/ para audio.
• Nombres de archivo siempre en minúsculas (evita bugs de case-sensitivity al pasar de Windows a un servidor Linux).
CSS
• Un solo <style> por plantilla, organizado en bloques con encabezados tipo /* ===== NOMBRE SECCIÓN ===== */, en el mismo orden en que las secciones aparecen visualmente en la página.
• Nunca dejar dos reglas para el mismo selector en el mismo archivo (la cascada las pisa silenciosamente) — al reemplazar una sección, borrar la vieja por completo.
• No usar el formateador automático (Prettier / "Format Document") sobre archivos .html que mezclan Django con HTML — sí usarlo libremente en .py.
Modelo de datos
• Datos que aplican a cualquier tipo de evento → columnas reales en Invitacion.
• Datos específicos de un tipo de evento (vestimenta, ceremonia/recepción, itinerario, mesa de regalos, admite_niños) → claves dentro de contenido_extra (JSON), documentadas de palabra por ahora; candidato a moverse a campos de formulario propios en el admin cuando haya clientes reales (evitar que un cliente edite JSON a mano).
Flujo de trabajo con el usuario
• En cada avance de código: explicar qué cambió, por qué, para qué sirve y el principio general detrás (acordado explícitamente como preferencia).
• Priorizar diseño antes que funcionalidades técnicas nuevas cuando ambas compiten por tiempo — la tesis del negocio es que en este nicho el diseño vende antes que la tecnología.
• Assets de diseño (imágenes, iconos) deben tener licencia de uso comercial clara, dado que el producto se vende a clientes y se promociona en Meta Ads.
6. Estado actual y pendientes
Terminado:
• Motor Django completo (modelos, admin, vistas, urls) funcionando de punta a punta.
• Primera plantilla de boda ("Terracota Velada") con diseño floral real, tipografía script + serif, scroll tipo pantalla-por-pantalla, RSVP en vivo, countdown, botones de ubicación (ceremonia/recepción separadas), vestimenta con color, itinerario, mesa de regalos, nota de niños, música con botón de reproducción manual.
• Probado end-to-end en compu y en iPhone real (por WiFi local).
• Demo de Terracota por comando (antes solo existía la armada a mano en el admin): python manage.py crear_demo_terracota [--host <ip>:8000] → /invitaciones/demo-boda-daniela-andres/.
• Plantilla de baby shower "Diez Lunas" (ver sección 7), con votación en vivo, calendario .ics y demo creada por comando; integrada con XV, graduación, fiesta y la PWA.
• Segunda plantilla de boda ("Cobalto Editorial", boda-editorial-02.html): concepto de revista de moda, opuesta a Terracota (fría, tipográfica, asimétrica). Paleta marfil/cobalto/tinta, Bodoni Moda + Schibsted Grotesk (OFL, sin assets de terceros). Si hay galería, la primera foto se vuelve portada en monotono cobalto. Demo: python manage.py crear_demo_cobalto [--host http://<ip>:8000].
• Segunda plantilla de XV años ("Carnet de Baile", xv-carnet-02.html): el carnet donde las damas apuntaban sus piezas en los bailes de gala; estética coquette (moños de satín, perlas, encaje festoneado, rosa ballet), opuesta a Medianoche Dorada. Ballet + Gilda Display (OFL), todo el arte es SVG propio. La invitación llega envuelta como regalo: al tocar el moño se desata y arranca la música (ese toque es la interacción que el navegador exige para el audio); el regalo nace con hidden y el resto de la página queda inert mientras está cerrado. Countdown como 4 perlas ensartadas, galería en camafeos ovalados, RSVP como "Carnet de baile". Demo: python manage.py crear_demo_xv_carnet [--host <ip>:8000] → /invitaciones/demo-xv-regina/.
• Segunda plantilla de graduación ("Tarea Cumplida", graduacion-cuaderno-02.html): la última hoja del cuaderno escolar, opuesta a Laurel de Oro (de día, con humor, memoria escolar mexicana). Libreta de cuadrícula con espiral y margen rojo, nombre pasado con marcatextos (trazo en multiply), "10 ¡Excelente!" en pluma roja, datos como lista palomeada con nota "¡esto viene en el examen!", countdown en recuadros hechos a mano, botones como cintas washi, itinerario como horario de clases, galería como periódico mural de corcho y RSVP como pase de lista en el pizarrón; al confirmar vuelan birretes. Caveat + Space Mono (OFL), garabatos SVG propios. Usa las mismas claves carrera/institucion/generacion que Laurel de Oro. Demo: python manage.py crear_demo_graduacion_cuaderno [--host <ip>:8000] → /invitaciones/demo-graduacion-diego/.
• Segunda plantilla de fiesta ("La Lotería", fiesta-loteria-02.html): la invitación como cartas de Lotería mexicana, opuesta a Noche Neón (de día, familiar, cualquier edad: cumpleaños, comida familiar, posada, fiesta patria). Papel picado ondeando, abanico de cartas con la del festejado al frente, datos como cartas de una tabla que se marcan con frijolitos ("¡Corre y se va!"), programa en tiras de cartón, fotos como cartas y RSVP como tabla; al confirmar aparece "¡Lotería!" con lluvia de papel picado. Solo se toma el FORMATO de carta (genérico); todas las ilustraciones son SVG propios, no el arte registrado de ninguna lotería comercial. Rye + Bricolage Grotesque (OFL). Claves propias: carta_numero, carta_titulo, carta_dibujo ("pastel" | "pinata"). Demo: python manage.py crear_demo_loteria [--host <ip>:8000] → /invitaciones/demo-loteria-lupita/.
• Segunda plantilla de baby shower ("Entrega Especial", baby-shower-entrega-02.html): el mito de la cigüeña llevado a hoy, el bebé es un paquete en camino. Opuesta a Diez Lunas (de día, cartón kraft, humor, neutral en género). Portada: caja con cinta de "FRÁGIL", sellos de hule y la guía de envío (Para, Contenido, Entrega estimada = fecha_probable_parto, código de barras y n.º de guía). Viste TODAS las secciones de baby shower del motor: la "dulce espera" es el rastreo del envío (las 10 lunas del motor se leen como paradas de la ruta; el JS marca el estatus Empacando / En tránsito / En reparto según la semana), "¿Qué trae el paquete?" para la votación con revelación como sello de hule, regalos como etiquetas de envío, pañales como tabla de destinos, fotos como timbres postales (máscara con orilla perforada) y RSVP como acuse de recibo que se sella con "¡RECIBIDO!". Big Shoulders Stencil + Courier Prime (OFL). Demo: python manage.py crear_demo_baby_entrega [--host <ip>:8000] → /invitaciones/demo-baby-entrega/ (fechas relativas a hoy).
• Tercera plantilla de boda ("Hotel Amor", boda-hotel-03.html): la boda como hotel boutique (tendencia de "hotel branding" en bodas), pensada para bodas en hacienda, hotel o destino, el cliente que más invierte. Opuesta a Terracota (floral) y a Cobalto (revista): paleta "old money" verde botella / crema / vino / latón (60-30-10). Portada con toldo de rayas festoneado, escudo ovalado con el monograma de la pareja (el JS saca las iniciales de anfitriones y pinta el "&" en vino), cinco estrellas y "Check-in" con la fecha. Info como confirmación de reservación (el JS renombra Día → Check-in, Código de vestimenta → Etiqueta del hotel), countdown en 4 relojes de lobby, itinerario en letrero de fieltro, mesa de regalos como "Concierge", la nota de niños como colgador de puerta ("No molestar" si es solo adultos, "Club de niños" si no), galería "Salón de retratos" en marcos de latón y RSVP como tarjeta de registro ("Hacer check-in"). Al confirmar con "Sí" el invitado recibe su llave: "Habitación N.º 024" = su lugar en la lista (escucha el evento rsvp:enviado del motor). La música es una campanita de recepción. Gloock + Josefin Sans (OFL), todo el arte es CSS/SVG propio. Demo: python manage.py crear_demo_hotel [--host <ip>:8000] → /invitaciones/demo-hotel-amor/.
• Tercera plantilla de XV años ("La Gira", xv-gira-03.html): la quinceañera como estrella pop y su fiesta como la única fecha de su gira; habla el idioma de las chavas de 15 (conciertos, photocards, pulseras de la amistad), que son quienes presumen la invitación. Opuesta a Medianoche Dorada (noche, dorado) y a Carnet de Baile (coquette): de día, pastel holográfico Y2K y cromo; paleta lila / tinta morada / chicle + holograma (60-30-10). Portada como póster de gira: marquesina con texto corriendo, nombre en letras cromadas (contorno con drop-shadow, no text-stroke: en fuente variable dibuja las uniones internas), XV gigante de fondo, mariposas y destellos, "Una sola fecha" con sticker "Entrada solo con invitación". Info como boleto de concierto (franja holográfica, talón perforado con la cuenta regresiva y código de barras; el JS renombra Día → Fecha, Código de vestimenta → Dress code). Itinerario como setlist pegado con cinta en el escenario (el último punto lleva "Encore"), familia como "Créditos", mesa de regalos como "Merch oficial", nota de niños como pulsera de acceso. Galería: el JS convierte las fotos en photocards firmadas (01/04) en carrusel horizontal (en escritorio, todas en fila). RSVP como pase VIP con lanyard; al confirmar con "Sí" el invitado recibe una pulsera de la amistad con su nombre en cuentas de letras (hasta 12), acomodada en elipse con perspectiva (escucha rsvp:enviado; el nombre se guarda en el submit porque el motor borra el form antes de avisar). Música: un CD holográfico que gira. Unbounded + Figtree (OFL) y Mrs Saint Delafield solo para la firma, pedida con &text=<nombre> para bajar un archivo diminuto. "Sáb" se arma con date:"l"|slice:":3" porque date:"D" de Django da "Sab" sin acento. Clave propia opcional: ciudad ("Guadalajara, Jal."). Demo: python manage.py crear_demo_xv_gira [--host <ip>:8000] → /invitaciones/demo-xv-ximena/ (ojo: demo-xv-valentina es de Medianoche Dorada).
• Tercera plantilla de graduación ("Próxima Salida", graduacion-salida-03.html): graduarse es despegar; la invitación es un aeropuerto. Opuesta a Laurel de Oro (noche, dorado, solemne) y a Tarea Cumplida (cuaderno, humor): señalética de aeropuerto, negro tablero + amarillo señal sobre cielo claro, rojo pista de acento. Portada: tablero de salidas con franja amarilla "Salidas" y reloj; el nombre se arma en paletas split-flap que giran hasta acomodarse (el h1 conserva el nombre en aria-label; sin JS se ve como letrero) y la fila del vuelo: Vuelo = generacion, Destino = carrera, Origen = institucion, Salida, Estatus (el JS pone "A tiempo" / "Abordando" a ≤7 días / "Despegó"). Info como pase de abordar (ESC → FUT, pasajero "Invitado especial", el JS renombra Día → Fecha, Hora → Abordaje, Código de vestimenta → Dress code) y countdown en paletas que voltean al cambiar. Itinerario como ruta de vuelo con escalas (el avión aterriza en la última), familia como "Tripulación" con alas de piloto, mesa de regalos como "Duty free", nota de niños como etiqueta de maleta. Fotos en ventanillas de avión con cortinita que sube al llegar. RSVP "Última llamada"; al confirmar con "Sí" el tablero agrega la fila del pasajero con su nombre y asiento (1A…6A, 1B… según su lugar en la lista) girando en paletas. Música: letrero de audífonos de a bordo. Barlow Condensed + Barlow (OFL), avión y alas SVG propios. Demo: python manage.py crear_demo_graduacion_salida [--host <ip>:8000] → /invitaciones/demo-graduacion-camila/.
• Tercera plantilla de fiesta ("Nivel Desbloqueado", fiesta-consola-03.html): la fiesta como videojuego retro y el celular del invitado se vuelve una consola portátil. Sirve para cumpleaños de cualquier edad ("Nivel 30 desbloqueado"), fiestas de oficina o de amigos. Opuesta a Noche Neón (antro, noche) y a La Lotería (tradición mexicana): plástico crema de consola, los cuatro verdes de una pantalla LCD y botones guinda. Portada: la consola con pantalla LCD (vidas en corazones de pixel, nombre en letra pixel, el mensaje se escribe letra por letra como diálogo de RPG, "▶ Presiona Start"). Los controles funcionan: A = música (hace click en el botón del motor, así el toque cuenta como interacción para el audio), B = ir al RSVP, START = bajar a la misión, SELECT = agendar (.ics) y la cruceta cambia de pantalla (apaga el scroll-snap un segundo, como el motor). Info como "Misión 1: Llega a la fiesta" en ventana de RPG; countdown como el "TIEMPO" del marcador. Itinerario como mapa de niveles (1-1, 1-2… META), mesa de regalos como "Tienda", nota de niños como modo de juego ("Multijugador" / "Modo +18"). Fotos como cartuchos ("Partidas guardadas"). RSVP "Insert coin"; al confirmar con "Sí" salen "+1UP" y la tabla de puntajes con el invitado como nuevo jugador. Pixelify Sans + VT323 (OFL): se descartó Press Start 2P porque encoge las mayúsculas con acento (MISIÓN se lee "MISIóN"), y los números del marcador van en VT323 porque en la letra pixel el 5 parece S. Clave propia opcional: nivel ("30"). Demo: python manage.py crear_demo_fiesta_consola [--host <ip>:8000] → /invitaciones/demo-fiesta-rodrigo/.
• Tercera plantilla de baby shower ("Pancito en el Horno", baby-shower-panaderia-03.html): "hay un pancito en el horno"; el bebé es pan recién hecho en una panadería mexicana. Opuesta a Diez Lunas (noche lavanda, poética) y a Entrega Especial (kraft, paquetería): cálida, antojable y muy mexicana; paleta crema de masa / chocolate / fresa + dorado de pan, azul talavera de acento. Portada: concha grande humeando bajo el letrero curvo "¡Hay un pancito en el horno!" (SVG textPath), chispas de colores y franja de azulejos de talavera. Viste TODAS las secciones de baby shower del motor: la dulce espera es "Tiempo de horneado" (el JS cambia las 10 lunas por 10 conchas en la charola: horneadas de sabores surtidos, la actual en el horno con vapor, las demás masa cruda); info como receta de la abuela sobre mantel de cuadritos (Cuándo / A qué hora / Dónde / Qué ponerse) con el reloj del horno "Sale del horno en"; programa como menú con puntitos; votación "¿De qué sabor viene?" con conchas de fresa o chocolate (la costra toma --color-opcion), revelación como etiqueta de pastel ondulada y lluvia de chispas; regalos como cajas de pastelería con cordón; pañales como etiquetas de precio; fotos sobre blondas de papel calado; nota de niños como galleta. RSVP "Pide tu turno" / hoja de pedido; al confirmar con "Sí" sale el ticket del turno (su lugar en la lista) con el nombre del invitado. Música: una conchita que se mece y humea. Truco: la concha se dibuja con <use>, y los selectores CSS no entran a la copia; los estados cambian variables (--pan, --costra, --surco) que sí se heredan. Young Serif + DM Sans (OFL). Demo: python manage.py crear_demo_baby_pancito [--host <ip>:8000] → /invitaciones/demo-baby-pancito/ (fechas relativas a hoy).
• PWA real (verificada en Chromium: service worker activo, manifest válido, abre sin internet): manifest generado por invitación en <slug>/manifest.webmanifest (nombre, ícono de la plantilla, colores, start_url y scope = la propia invitación), service worker en /invitaciones/sw.js (red-primero para el HTML, caché-primero para imágenes y fuentes; nunca cachea /rsvp/ ni /votar/ ni POST ni audio por rangos) e íconos 180/192/512 por plantilla (+ etiquetas de Apple para iPhone). OJO: el service worker solo se activa en HTTPS o localhost; por WiFi con http://<ip> la invitación funciona pero no se instala ni trabaja sin señal.
• Probar en el celular: python manage.py crear_todos_los_demos --host <ip>:8000 crea/actualiza los 15 demos e imprime sus links. Para probar la PWA (instalar, sin señal) se necesita HTTPS: cloudflared tunnel --url http://localhost:8000 (o ngrok) y abrir el https://… que da. En DEBUG, CSRF_TRUSTED_ORIGINS acepta *.trycloudflare.com y *.ngrok-free.app (sin eso el RSVP da 403 por el Origin del túnel).
• Invitacion.musica_src: si musica_url apunta a nuestro /static/, el <audio> usa solo la ruta; así la música suena igual por la IP, localhost, el túnel o el servidor final (antes dependía de la IP con que se creó el demo y fallaba al cambiar de red o al abrir por HTTPS, por contenido mixto).
• Listo para producción (ver DESPLIEGUE.md, hosting recomendado: PythonAnywhere por disco permanente para SQLite y fotos, HTTPS Let's Encrypt automático, tareas programadas y Python 3.13):
  – settings.py = desarrollo (sin cambios para runserver); settings_produccion.py importa todo y fija DEBUG=False, SECRET_KEY/ALLOWED_HOSTS/DJANGO_ADMIN_URL desde .env (python-dotenv, cargado ANTES de importar settings.py porque éste también lee variables del aviso), CSRF_TRUSTED_ORIGINS derivados de los hosts, cookies Secure, WhiteNoise con CompressedManifestStaticFilesStorage (soporta Range para el audio en iPhone), caché en archivo (compartida entre procesos para el rate limit), LOGGING a stderr (el error log del hosting) y MAILERS SMTP (Django 6.1 marca error mail.E001 si queda el backend de consola). Sin .env obligatorio, no arranca (ImproperlyConfigured). wsgi.py/asgi.py usan producción por defecto; runserver no pasa por ahí. DJANGO_PROXY_HTTPS=1 activa SECURE_PROXY_SSL_HEADER + redirect + HSTS; si no, el hosting fuerza HTTPS y se silencian W004/W008.
  – RSVP validado en el servidor (nombre 1–150, asistencia de las opciones, acompañantes 0–MAX_ACOMPANANTES, mensaje ≤1000; errores 400 con mensaje que el motor muestra en #rsvp-status) y el mismo nombre + respuesta en 10 min no cuenta doble. Rate limit (invitaciones/limites.py) en RSVP y votos: LIMITES_RSVP / LIMITES_VOTO = 10 por conexión cada 10 min y 300 por invitación por hora → 429 + Retry-After; la IP sale de CABECERA_IP_CLIENTE (PythonAnywhere: HTTP_X_REAL_IP, porque REMOTE_ADDR es el balanceador y sería igual para todos) y solo se guarda como hash con la SECRET_KEY en la caché. El motor apaga el botón mientras envía (doble toque).
  – Aviso de privacidad integral en /privacidad/ (datos del responsable desde .env; si faltan salen entre corchetes y check --deploy da invitaciones.W001) + aviso corto bajo cada RSVP en el motor (tamaño en em: en letras pixel 12px no se leían). borrar_datos_vencidos borra RSVP y votos DIAS_RETENCION_DATOS (90) días después del evento, lo que promete el aviso.
  – respaldar_bd [--fotos] [--conservar 14]: copia consistente con la API de backup de SQLite, PRAGMA integrity_check, gzip, rotación; restauración en DESPLIEGUE.md. 404/500 propias sin detalles técnicos. requirements.txt limpio (antes era un pip freeze de toda la compu).
• Todos los demos siguen el patrón demo-<tipo>-<festejado>: los tres primeros se renombraron (demo-fiesta → demo-fiesta-sofia, demo-graduacion → demo-graduacion-valeria-montes, baby-shower-demo → demo-baby-mariana-diego); su comando renombra el registro viejo si existe, así no se pierden fotos ni confirmaciones. demo-xv-valentina ya cumplía el patrón.
Pendiente dentro de Fase 1:
• Estilizar en la plantilla de boda las secciones nuevas del motor (regalos con lista, lluvia de sobres) si algún cliente de boda las pide; la votación no aparece ahí porque soporta_votacion=False.
• Revelar el resultado de la votación desde un botón del admin en vez de editar el JSON (hoy: "resultado": "nina" dentro de "votacion").
• Estilizar en Cobalto Editorial y Hotel Amor las secciones nuevas del motor (regalos con lista, lluvia de sobres) si algún cliente de boda las pide.
• Decidir si musica_url pasa de URLField a FileField para que la carga de canciones sea vía admin en vez de URLs manuales.
• Decidir si los campos de contenido_extra (ceremonia/recepción, vestimenta, etc.) se formalizan como campos de admin dedicados antes de vender a clientes reales, para evitar que alguien edite JSON a mano.
• Créditos/atribución pendientes por confirmar en los assets gratuitos de Flaticon usados (iconos), según la licencia exacta de cada uno descargado.
• Contratar hosting y dominio y seguir DESPLIEGUE.md; que un abogado revise el texto de /privacidad/ antes del primer cliente.
• Respaldo fuera del servidor: hoy es descarga manual semanal (automatizar a Drive/S3 cuando haya clientes).
No iniciado todavía: Fase 2 (precios), Fase 3 (Meta Ads), Fase 4 (venta por WhatsApp).
7. Plantilla Baby Shower "Diez Lunas" (baby-shower-lunas-01)
Concepto: un embarazo dura 280 días = diez lunas de 28. Cielo lavanda al atardecer con un móvil de cuna (luna, estrellas, nube, corazón) meciéndose, y una pantalla de noche donde las lunas se llenan según la semana real del embarazo. Todo el arte es SVG propio dentro del template (sin imágenes descargadas → sin dudas de licencia). Tipografía: Fraunces (itálica "suave") + Nunito. Paleta neutra por defecto (tendencia 2026), variantes con contenido_extra.paleta = "rosa" | "azul".
Pantallas (cada una aparece solo si hay datos):
1. Hero — "Baby Shower" + anfitriones + mensaje.
2. Dulce espera — semana actual, 10 lunas con su fase, días que faltan, tamaño del bebé comparado con una fruta. Se recalcula con la fecha de hoy del invitado.
3. Info — tarjeta con Día/Hora, Lugar (+ dirección), vestimenta con varios colores, countdown y botones Confirmar / Ubicación / Agendar.
4. Juego en vivo "¿Niña o niño?" — votos con barras que se llenan; resultados visibles al votar. Solo premium + plantilla con soporta_votacion. Al poner el resultado en el admin, a todos los que tienen la invitación abierta les aparece "¡Es niña!" con confeti en ≤ 8 s (mismo polling del RSVP).
5. Regalos — mesas de regalos (con botón "Copiar número" de evento Liverpool) y lluvia de sobres.
6. Lluvia de pañales — tabla de tallas por inicial del apellido + buscador "¿Cuál me toca?".
7. Galería (polaroids) y RSVP (el mensaje se pide como "deseo o consejo para el bebé").
Motor (sirve para cualquier plantilla futura):
• Modelo Voto + Plantilla.soporta_votacion (default False), migración 0003. Endpoints: <slug>/votar/, <slug>/votar/conteo/ (excluidos de la caché del service worker, igual que /rsvp/).
• <slug>/calendario.ics — botón "Agendar" (ícono SVG) en todas las plantillas (recordatorio 1 día antes, duración 4 h). Con 4 botones, boda/XV/graduación los acomodan 2 × 2 en celular.
• Evento con un solo lugar: usa las columnas lugar_nombre / lugar_mapa_url (antes no se mostraban).
• Bloque theme_color: por defecto usa plantilla.color_tema; Diez Lunas lo cambia según la paleta. Ícono de app propio en static/invitaciones/pwa/baby-shower-lunas-01-*.png.
Claves de contenido_extra (todas opcionales):
• fecha_probable_parto: "2027-02-06" (activa "Dulce espera")
• bebe_nombre: "Emilia" (si no hay, dice "al bebé")
• lugar_direccion: "Av. Francisco Sosa 215, Coyoacán"
• dresscode_colores: ["#EBB7C5", "#A9C8E8"] (lista; dresscode_color sigue funcionando)
• votacion: {"pregunta", "subtitulo", "opciones": [{"clave", "texto", "color", "revelacion"}], "resultado": ""}
• mesas_regalos: [{"nombre", "codigo", "url"}]
• lluvia_sobres: "texto"
• lluvia_panales: [{"desde": "A", "hasta": "F", "talla": "Etapa 1"}, ...]
• paleta: "rosa" | "azul" (solo Diez Lunas)
Demo: python manage.py crear_demo_baby_shower → /invitaciones/demo-baby-mariana-diego/ (fechas relativas a hoy, se puede correr de nuevo).
