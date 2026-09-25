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
• Plantilla de baby shower "Diez Lunas" (ver sección 7), con votación en vivo, calendario .ics y demo creada por comando; integrada con XV, graduación, fiesta y la PWA.
Pendiente dentro de Fase 1:
• Estilizar en la plantilla de boda las secciones nuevas del motor (regalos con lista, lluvia de sobres) si algún cliente de boda las pide; la votación no aparece ahí porque soporta_votacion=False.
• Revelar el resultado de la votación desde un botón del admin en vez de editar el JSON (hoy: "resultado": "nina" dentro de "votacion").
• PWA: manifest.json + service worker (aún no se ha tocado esta parte).
• Decidir si musica_url pasa de URLField a FileField para que la carga de canciones sea vía admin en vez de URLs manuales.
• Decidir si los campos de contenido_extra (ceremonia/recepción, vestimenta, etc.) se formalizan como campos de admin dedicados antes de vender a clientes reales, para evitar que alguien edite JSON a mano.
• Créditos/atribución pendientes por confirmar en los assets gratuitos de Flaticon usados (iconos), según la licencia exacta de cada uno descargado.
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
Demo: python manage.py crear_demo_baby_shower → /invitaciones/baby-shower-demo/ (fechas relativas a hoy, se puede correr de nuevo).
