# Publicar las invitaciones en internet (hosting + dominio + HTTPS)

Guía paso a paso para pasar de "corre en mi compu por WiFi" a un link real
que le puedes mandar a un cliente (`https://www.tudominio.mx/invitaciones/...`).

Se usa **PythonAnywhere** porque encaja con cómo está hecho el proyecto:

- Es hosting especializado en Python/Django, sin Docker ni servidores que administrar.
- El disco es permanente: la base SQLite y las fotos que subes desde el admin
  no se borran al reiniciar (en otros hostings gratuitos sí se borran).
- Da HTTPS gratis (Let's Encrypt) que se renueva solo, y tiene un interruptor
  "Force HTTPS".
- Tiene tareas programadas para los respaldos diarios.
- Tiene Python 3.13 (Django 6.1 necesita 3.12 o más).

Puedes empezar **gratis** con `tuusuario.pythonanywhere.com` (ya con HTTPS)
para probar todo; el **dominio propio** necesita un plan de paga (a sep-2026,
el plan "Developer" cuesta alrededor de US$10/mes; revisa el precio actual en
su página antes de contratar).

---

## 0. Lo que cambió en el proyecto para producción

| Qué | Dónde | Para qué |
|---|---|---|
| Settings separados | `invitaciones_core/settings_produccion.py` | `DEBUG=False` siempre, secretos desde `.env`, cookies solo por HTTPS |
| Secretos fuera del código | `.env` (solo en el servidor), plantilla en `.env.ejemplo` | La `SECRET_KEY` de `settings.py` ya es pública en git: producción usa otra |
| Archivos estáticos | WhiteNoise | Con `DEBUG=False`, Django ya no sirve `/static/` |
| Anti-spam en RSVP y votos | `invitaciones/limites.py` | Máx. 10 envíos por conexión cada 10 min y 300 por invitación por hora |
| Validación del RSVP | `views.py` | Datos malos → mensaje claro (antes, error 500) |
| Aviso de privacidad | `/privacidad/` + aviso corto bajo cada RSVP | LFPDPPP |
| Borrado de datos viejos | `manage.py borrar_datos_vencidos` | Lo que promete el aviso: RSVP y votos se borran 90 días después del evento |
| Respaldos | `manage.py respaldar_bd --fotos` | Copia diaria de la base y las fotos |
| Páginas de error | `404.html`, `500.html` | Mensaje amable, sin mostrar código |
| Ruta del admin | `DJANGO_ADMIN_URL` en `.env` | Que los bots no encuentren `/admin/` |

En tu compu **no cambia nada**: `python manage.py runserver` sigue usando
`settings.py` (desarrollo).

---

## 1. Crear la cuenta y subir el código

1. Crea una cuenta en <https://www.pythonanywhere.com> (empieza con la gratuita).
2. Abre una consola **Bash** (pestaña *Consoles*) y clona el repositorio.
   Si es privado, GitHub te pedirá usuario y un *token* (GitHub → Settings →
   Developer settings → Personal access tokens, con permiso de solo lectura
   al repositorio) en lugar de tu contraseña:

   ```bash
   git clone https://github.com/fabrizio-espinoza/project-digital-invitations.git Project-Digital-Invitations
   cd Project-Digital-Invitations
   ```

3. Crea el entorno virtual e instala las dependencias:

   ```bash
   mkvirtualenv --python=/usr/bin/python3.13 invitaciones
   pip install -r requirements.txt
   ```

4. Haz que la consola use siempre los settings de producción:

   ```bash
   echo 'export DJANGO_SETTINGS_MODULE=invitaciones_core.settings_produccion' >> ~/.virtualenvs/invitaciones/bin/postactivate
   workon invitaciones
   ```

## 2. El archivo `.env` (los secretos)

```bash
cp .env.ejemplo .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
nano .env
```

Pega la llave que generó el segundo comando en `DJANGO_SECRET_KEY` y llena:

- `DJANGO_ALLOWED_HOSTS`: por ahora `tuusuario.pythonanywhere.com`. Cuando
  tengas dominio: `www.tudominio.mx,tudominio.mx,tuusuario.pythonanywhere.com`.
- `DJANGO_ADMIN_URL`: una ruta difícil de adivinar (ej. `panel-7k2q`).
- `DJANGO_CABECERA_IP=HTTP_X_REAL_IP` (así llega la IP real del invitado en
  PythonAnywhere; sin esto el límite anti-spam trataría a todos como uno solo).
- `WHATSAPP_NUMERO`: tu WhatsApp de ventas, 52 + 10 dígitos (ej. `525512345678`).
  Es a donde llegan los botones "La quiero" del catálogo.
- Los datos del aviso de privacidad (`MARCA_NOMBRE`, `AVISO_RESPONSABLE`,
  `AVISO_DOMICILIO`, `AVISO_CORREO`).

El `.env` **nunca** se sube a git (ya está en `.gitignore`).

## 3. Base de datos, estáticos y usuario del admin

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser        # usa una contraseña larga y única
python manage.py check --deploy         # debe decir "no issues"
```

`check --deploy` revisa la seguridad y además avisa si faltan los datos del
aviso de privacidad o si el admin sigue en `/admin/`.

## 4. Crear la web app

`TUUSUARIO` va **exactamente** como tu usuario, con mayúsculas si las tiene
(`/home/InvitaVibra/...` y `/home/invitavibra/...` son carpetas distintas en
el servidor). Para verla: `cd ~/Project-Digital-Invitations && pwd`.

Pestaña **Web** → *Add a new web app* → *Manual configuration* → **Python 3.13**.

1. **Virtualenv**: `/home/TUUSUARIO/.virtualenvs/invitaciones`
2. **Source code**: `/home/TUUSUARIO/Project-Digital-Invitations`
3. **WSGI configuration file** (liga en la misma página): borra todo y deja:

   ```python
   import os
   import sys

   ruta = '/home/TUUSUARIO/Project-Digital-Invitations'
   if ruta not in sys.path:
       sys.path.insert(0, ruta)

   os.environ['DJANGO_SETTINGS_MODULE'] = 'invitaciones_core.settings_produccion'

   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```

4. **Static files** (sección de la misma pestaña), agrega dos:

   | URL | Directory |
   |---|---|
   | `/static/` | `/home/TUUSUARIO/Project-Digital-Invitations/staticfiles` |
   | `/media/` | `/home/TUUSUARIO/Project-Digital-Invitations/media` |

   La de `/media/` es **obligatoria**: sin ella las fotos de galería no se ven
   (WhiteNoise sirve `/static/`, no las fotos subidas).

5. **Security** → activa **Force HTTPS**.
6. Botón verde **Reload**.

Prueba: `https://tuusuario.pythonanywhere.com/` (el catálogo),
`https://tuusuario.pythonanywhere.com/privacidad/` y el admin en
`https://tuusuario.pythonanywhere.com/panel-7k2q/`.

## 5. Crear los demos en el servidor

```bash
python manage.py crear_todos_los_demos --host https://tuusuario.pythonanywhere.com
```

Imprime los 15 links. Sube las fotos de galería desde el admin.

## 6. Dominio propio + HTTPS

1. Compra el dominio (`.mx` o `.com.mx` en registradores como Akky, Neubox o
   GoDaddy; `.com` en Namecheap, Cloudflare, etc.).
2. Cambia tu cuenta de PythonAnywhere a un plan de paga.
3. Pestaña **Web** → *Add a new web app* con el nombre `www.tudominio.mx`
   (repite el paso 4 con la misma configuración), o cambia el dominio de la
   que ya tienes. PythonAnywhere te muestra un valor tipo
   `webapp-XXXXXX.pythonanywhere.com`.
4. En tu registrador, en la zona DNS:
   - Registro **CNAME**: `www` → `webapp-XXXXXX.pythonanywhere.com`
   - El dominio "pelón" (`tudominio.mx`, sin www) no puede ser CNAME: usa el
     **redireccionamiento** del registrador hacia `https://www.tudominio.mx`.
5. Espera a que propague el DNS (minutos a unas horas).
6. Pestaña **Web** → *Security* → *HTTPS certificate* → **Auto-renewing
   Let's Encrypt certificate**. Deja activado **Force HTTPS**.
7. Agrega los dominios a `DJANGO_ALLOWED_HOSTS` en `.env` y dale **Reload**.

Ahora el link que mandas al cliente es
`https://www.tudominio.mx/invitaciones/<slug>/`, y la PWA ya se puede instalar
en cualquier celular.

## 7. Respaldos y limpieza diarios (tarea programada)

Pestaña **Tasks** → tarea **diaria** (la hora está en UTC; 09:00 UTC = 3:00 a.m. en CDMX):

```bash
cd /home/TUUSUARIO/Project-Digital-Invitations && export DJANGO_SETTINGS_MODULE=invitaciones_core.settings_produccion && /home/TUUSUARIO/.virtualenvs/invitaciones/bin/python manage.py borrar_datos_vencidos && /home/TUUSUARIO/.virtualenvs/invitaciones/bin/python manage.py respaldar_bd --fotos
```

- `borrar_datos_vencidos`: borra RSVP y votos de eventos que pasaron hace
  más de 90 días (lo que dice el aviso de privacidad). Para ver qué borraría
  sin borrar nada: `--simular`.
- `respaldar_bd --fotos`: deja en `respaldos/` la base (`bd-FECHA.sqlite3.gz`)
  y las fotos (`fotos-FECHA.tar.gz`), revisa que la copia no esté dañada y
  conserva las 14 más recientes.

**Importante:** esos respaldos viven en el mismo servidor. Si pierdes la
cuenta, los pierdes también. Una vez por semana descarga el más reciente
(pestaña **Files** → carpeta `respaldos/` → descargar) y guárdalo en tu
Drive o en tu compu.

### Restaurar un respaldo

```bash
cd ~/Project-Digital-Invitations
gunzip -c respaldos/bd-2026-10-05_030000.sqlite3.gz > db.restaurada.sqlite3
mv db.sqlite3 db.antes-de-restaurar.sqlite3
mv db.restaurada.sqlite3 db.sqlite3
tar xzf respaldos/fotos-2026-10-05_030000.tar.gz     # solo si también quieres las fotos
```

Luego **Reload** en la pestaña Web.

## 8. Actualizar el sitio cuando haya cambios

```bash
cd ~/Project-Digital-Invitations
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Y **Reload** en la pestaña Web.

## 9. Si algo falla

Con `DEBUG=False` los errores ya no salen en pantalla (a propósito). Ve a
la pestaña **Web** → *Log files* → **error log**: ahí está el detalle.
Ahí mismo aparecen los avisos de "Límite de rsvp superado" cuando alguien
intenta mandar confirmaciones masivas.

## Lista antes del primer cliente

- [ ] `python manage.py check --deploy` sin avisos.
- [ ] `/privacidad/` muestra tus datos reales (nada entre corchetes). Que lo
      revise un abogado: es una plantilla bien armada, no asesoría legal.
- [ ] El admin tiene ruta propia y contraseña larga.
- [ ] Confirmaste un RSVP desde tu celular con datos móviles (no WiFi).
- [ ] Instalaste la invitación como app y abrió en modo avión.
- [ ] La tarea diaria corrió al menos una vez y descargaste un respaldo.
