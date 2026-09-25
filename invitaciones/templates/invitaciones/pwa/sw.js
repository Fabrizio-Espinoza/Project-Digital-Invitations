// Service worker de las invitaciones: un script que el navegador instala
// "aparte" de la página y que se para en medio de cada petición de red.
// Sirve para dos cosas:
//   1. Que la invitación se pueda instalar como app (Android lo exige).
//   2. Que la invitación abra aunque el invitado esté sin señal (salón,
//      jardín, iglesia) mostrando la última versión que ya vio.
//
// Para forzar que todos los celulares tiren su caché vieja, sube VERSION.
const VERSION = 'v1';
const CACHE = `invitaciones-${VERSION}`;

self.addEventListener('install', () => {
    // activa la versión nueva sin esperar a que el invitado cierre la app
    self.skipWaiting();
});

self.addEventListener('activate', (evento) => {
    // borra las cachés de versiones anteriores
    evento.waitUntil(
        caches.keys()
            .then(nombres => Promise.all(
                nombres
                    .filter(nombre => nombre.startsWith('invitaciones-') && nombre !== CACHE)
                    .map(nombre => caches.delete(nombre))
            ))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (evento) => {
    const peticion = evento.request;
    const url = new URL(peticion.url);

    // Nunca se guarda en caché:
    // - POST (el envío del RSVP)
    // - todo lo de /rsvp/ y /votar/ (los conteos y la revelación del juego
    //   en vivo deben ser siempre los reales, no una copia vieja)
    // - peticiones con "Range" (el audio se pide por pedazos y la caché
    //   no sabe responder pedazos)
    // - el admin
    if (peticion.method !== 'GET') return;
    if (url.pathname.includes('/rsvp/') || url.pathname.includes('/votar/')) return;
    if (peticion.headers.has('range')) return;
    if (url.pathname.startsWith('/admin/')) return;

    if (peticion.mode === 'navigate') {
        evento.respondWith(redPrimero(peticion));
        return;
    }

    const esMismoSitio = url.origin === self.location.origin;
    const esFuente = url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com';
    if (esMismoSitio || esFuente) {
        evento.respondWith(cachePrimero(evento));
    }
});

// La página HTML: primero la red (así el invitado ve cambios de último
// minuto, como una hora corregida); si no hay señal, la copia guardada.
async function redPrimero(peticion) {
    const cache = await caches.open(CACHE);
    try {
        const respuesta = await fetch(peticion);
        if (respuesta.ok) cache.put(peticion, respuesta.clone());
        return respuesta;
    } catch (error) {
        const guardada = await cache.match(peticion);
        if (guardada) return guardada;
        throw error;
    }
}

// Imágenes, fuentes y demás: se responde al instante con lo guardado y se
// actualiza la copia en segundo plano para la siguiente visita.
async function cachePrimero(evento) {
    const peticion = evento.request;
    const cache = await caches.open(CACHE);
    const guardada = await cache.match(peticion);
    const deRed = fetch(peticion)
        .then(respuesta => {
            // "opaque" = respuesta de otro dominio sin CORS (el CSS de Google Fonts)
            if (respuesta.ok || respuesta.type === 'opaque') {
                cache.put(peticion, respuesta.clone());
            }
            return respuesta;
        })
        .catch(() => guardada);
    // waitUntil: que el navegador no apague el SW antes de terminar de
    // actualizar la copia, aunque ya hayamos respondido con la guardada
    evento.waitUntil(deRed);
    return guardada || deRed;
}
