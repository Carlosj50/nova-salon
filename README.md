# Servicio IA Negocios

> Estado de licencia: repositorio publico para ver y evaluar. No es open source ni se autoriza su uso, copia, modificacion o despliegue sin permiso expreso.

Demo local de atención automática para peluquería / estética. El objetivo es enseñar en menos de un minuto cómo el negocio puede responder FAQs, registrar clientes y dejar solicitudes de cita organizadas.

## Qué incluye

- Chat web con FastAPI y HTML.
- Respuestas a horarios, servicios, precios, ubicación y contacto.
- Selección prudente de servicios por alias, intención y modificadores como caballero, mujer, infantil o barba.
- Chat con mejor continuidad: entiende respuestas breves, acepta frases como `mañana a las 17 mechas` y conserva ofertas cortas de reserva.
- El contexto corto del chat caduca tras inactividad para evitar que una respuesta vieja arrastre la conversación actual.
- El chat aprovecha mejor datos fuera de orden: si el cliente da antes el nombre o el teléfono, los guarda y luego pide solo lo que falta.
- Cuando ya solo falta un dato, responde más corto y directo.
- Flujo de cita con teléfono, cliente, servicio, fecha normalizada y hora normalizada.
- Las citas guardan una referencia estable al servicio para no romper histórico ni disponibilidad al renombrarlo.
- Franja opcional (`mañana`, `tarde`, `noche`) como apoyo, sin sustituir a la hora final.
- Cuando una hora no encaja, el sistema propone huecos cercanos del mismo día o del siguiente día abierto si los encuentra.
- Si el cliente ya pidió `mañana`, `tarde` o `noche`, las propuestas intentan respetar esa franja antes de abrir otras opciones.
- Base SQLite local en `demo/data/negocio.db`.
- Tabla de clientes y tabla de citas.
- Agenda interna en `/agenda`.
- Vista agenda visual en `/agenda/visual`, inspirada en una agenda de papel pero con acciones digitales.
- La agenda ahora destaca mejor qué requiere atención y muestra acciones rápidas sobre pendientes y siguiente cita.
- Alta manual de citas en `/citas/nueva`.
- Edición simple de citas en `/citas/{id}/editar`.
- Vista mensual simple dentro de `/agenda`, con clic por día.
- Lista de clientes en `/clientes`.
- Ficha de cliente con historial en `/clientes/{id}`.
- Edición simple de cliente en `/clientes/{id}/editar`.
- Gestión simple de servicios en `/servicios`.
- Gestión simple de personal y capacidad base en `/personal`.
- Configuración básica del negocio editable desde interfaz en `/config/negocio`.
- Nombre y logo del negocio editables desde `/config/negocio`, con reflejo directo en cabecera y login.
- La subida de logo acepta PNG, JPG/JPEG o WEBP hasta 5 MB. SVG queda fuera para reducir una superficie innecesaria en un panel interno simple.
- Centro de configuración en `/config` para ubicar negocio, acceso admin, WhatsApp, servicios y personal sin perderse entre pantallas.
- Configuración de canales en SQLite, empezando por WhatsApp.
- Si el mensaje entra por WhatsApp con número conocido, el sistema reconoce a la clienta, reutiliza su ficha y no vuelve a pedir teléfono.
- Acceso interno simple con usuarios `admin` y `staff`, más un acceso bootstrap por entorno/config para arranque o emergencia.
- Landing comercial en `landing/index.html`.

## Estructura útil

```text
demo/        app web, lógica del asistente, SQLite, plantillas y estilos
demo/core/   núcleo operativo, citas, disponibilidad y lógica conversacional
demo/web/    contexto web, routers web y helpers de agenda/formularios
landing/     página comercial simple para enseñar el valor
docs/        documentación operativa
scripts/     guion corto de captación
```

Guia visual recomendada para enseñar la app a negocio real:

- [docs/GUIA_VISUAL_USO.md](/mnt/h/servicio_ia_negocios/docs/GUIA_VISUAL_USO.md)

## Organización interna

La app sigue siendo pequeña, pero ya no deja todo el peso en dos archivos gigantes.

- `demo/app.py` se centra en arrancar FastAPI y conectar rutas.
- `demo/web/context.py` concentra contexto web reutilizable:
  - carga de negocio
  - auth simple
  - sesión del chat
- `demo/web/routes_agenda.py` agrupa agenda lista, agenda visual y acciones rápidas ligadas a agenda.
- `demo/web/routes_public.py` agrupa login, logout, chat público y healthcheck.
- `demo/web/routes_config.py` agrupa configuración del negocio, acceso, usuarios y canal WhatsApp.
- `demo/web/view_helpers.py` agrupa helpers de agenda, formularios y presentación.
- La autorización interna se mantiene simple: cada ruta protegida decide si exige acceso operativo (`staff` o `admin`) o acceso admin.
- `demo/core/bot_logic.py` mantiene la orquestación conversacional.
- `demo/core/chat_booking.py` separa el flujo de reserva.
- `demo/core/chat_state.py`, `demo/core/chat_text.py` y `demo/core/chat_channels.py` separan estado, parsing y contexto de canal para bajar fragilidad.

## Ejecutar la demo

Si vas a ejecutar el proyecto desde Windows PowerShell, usa:

```powershell
cd H:\servicio_ia_negocios
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\
.\.venv\Scripts\python.exe -m uvicorn demo.app:app --reload --host 0.0.0.0 --port 8000

```

Si lo ejecutas desde WSL/Linux, usa:

```bash
cd /mnt/h/servicio_ia_negocios
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn demo.app:app --reload
.venv/bin/python -m uvicorn demo.app:app --reload --host 0.0.0.0 --port 8000

```

Abre en el navegador:

```text
http://127.0.0.1:8000
```

La base `demo/data/negocio.db` se crea automáticamente al arrancar la app.

## Artefactos locales

El repo conserva el código, plantillas, datos base y documentación. Se quedan fuera los artefactos de trabajo local:

- `demo/data/negocio.db` y otras bases SQLite generadas en local
- `demo/data/uploads/` y logos subidos desde configuración
- `.env` y otros secretos locales
- `__pycache__/`, logs, zips y temporales de entrega

Si preparas un zip para compartir o revisar, deja fuera `.git`, `.venv`, la base local y los uploads generados.

## Ejecutar tests

La suite es pequeña y va al grano. Se centra en la lógica más frágil del proyecto.

Desde Windows PowerShell:

```powershell
cd H:\servicio_ia_negocios
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Desde WSL/Linux:

```bash
cd /mnt/h/servicio_ia_negocios
.venv/bin/python -m unittest discover -s tests -v
```

Ahora mismo cubre:

- normalización y validación básica de teléfono
- reutilización de cliente por teléfono
- auth simple: login, logout y protección de rutas internas
- parsing básico de fecha/hora
- selección de servicios con modificadores
- aclaraciones cortas del chat
- creación simple de cita por flujo conversacional
- bloqueo básico de disponibilidad por solape/capacidad
- creación y edición de cita a través del servicio central de citas
- creación manual de cita desde ruta interna
- edición de cita desde ruta interna

## Núcleo de citas

La creación y edición de citas ya no dependen solo de validaciones repartidas por chat y panel. El proyecto usa una capa central en `demo/core/appointment_service.py` para:

- validar fecha, hora y estado
- resolver el servicio real
- comprobar disponibilidad antes de escribir
- reutilizar o crear cliente cuando corresponde
- guardar o editar la cita en un único flujo

Chat y panel pasan por esa capa para reducir fragilidad antes de futuras integraciones.

## Acceso al panel interno

El chat público sigue disponible en `/`.

Las rutas internas ahora piden login:

```text
/agenda
/agenda/visual
/clientes...
/citas...
/servicios...
/personal...
/config...
```

Pantallas de acceso:

```text
/login   entrar al panel
/logout  cerrar sesión
```

La app admite esta configuración por entorno:

```text
APP_ADMIN_USERNAME
APP_ADMIN_PASSWORD
APP_SESSION_SECRET
APP_SESSION_COOKIE
```

Puedes copiar [.env.example](/mnt/h/servicio_ia_negocios/.env.example) a un `.env` local y ajustar ahí tus credenciales de desarrollo sin dejar secretos reales dentro del repo.

La carga normal de negocio ya es solo lectura. La parte que siembra catálogo, personal base y backfill de citas se ejecuta en una inicialización separada al arrancar la app.

El acceso bootstrap por entorno solo manda si están definidas a la vez estas dos variables:

```text
APP_ADMIN_USERNAME
APP_ADMIN_PASSWORD
```

Si falta una de las dos, el sistema ignora ese override parcial para no mezclar usuario y contraseña de fuentes distintas. En ese caso vuelve a usar, por este orden:

1. acceso guardado desde panel
2. config local

Si las dos variables bootstrap están definidas en entorno, ese acceso manda sobre el panel y la pantalla `/config/acceso` queda en solo lectura para evitar ambigüedades.

En `demo/data/negocio.json` solo quedan valores locales y claramente ficticios:

```json
"auth": {
  "admin_username": "admin",
  "admin_password": "local-dev-change-me",
  "session_secret": "local-dev-session-secret-change-me",
  "session_cookie": "nova_panel_session"
}
```

Para algo más serio que una demo local:

- usa variables de entorno
- cambia contraseña y secreto de sesión
- no reutilices los valores de ejemplo del repo

Los formularios internos del panel ya incluyen protección CSRF básica para reducir envíos cruzados no deseados.

## Rutas

```text
/                 chat de cliente
/login            acceso al panel con bootstrap admin o usuario interno
/logout           cierre de sesión
/agenda           agenda interna
/agenda/visual    agenda visual tipo planning
/citas/nueva      alta manual rápida de cita
/citas/{id}/editar edición simple de cita
/clientes         listado de clientes
/clientes/{id}    ficha e historial de un cliente
/clientes/{id}/editar edición simple de cliente
/servicios        listado y gestión simple de servicios
/servicios/nuevo  crear servicio
/servicios/{id}/editar editar servicio
/personal         listado simple de personal y capacidad por categoría
/personal/nuevo   crear persona
/personal/{id}/editar editar persona
/config           centro de configuración
/config/negocio   datos básicos del negocio
/config/acceso    usuario y contraseña admin
/config/usuarios  usuarios internos admin/staff
/config/canales   resumen de canales
/config/canales/whatsapp configuración rápida de WhatsApp
/health           comprobación técnica
```

## Probar el flujo

Ejemplo cliente nuevo:

```text
Cliente: Quiero cita mañana a las 17
Bot: ¿Qué teléfono de contacto dejamos?
Cliente: 600 111 222
Bot: No encuentro ese teléfono en la agenda todavía. ¿A nombre de quién registro la ficha?
Cliente: Ana López
Bot: ¿Qué servicio quieres reservar?
Cliente: tinte
Bot: He creado la ficha de Ana López y registrado la solicitud de cita...
```

Ejemplo cliente existente:

```text
Cliente: Quiero cita viernes a las 17 para corte de caballero
Bot: ¿Qué teléfono de contacto dejamos?
Cliente: 600111222
Bot: Perfecto, Ana López. He registrado una nueva solicitud de cita...
```

Ejemplo por WhatsApp con número conocido:

```text
Abrir /?channel=whatsapp&incoming_phone=600111222
Cliente: Hola
Bot: Hola Ana, te tengo registrada. ¿En qué te ayudo?

Cliente: Quiero cita mañana a las 17
Bot: Hola Ana. Perfecto, ya tengo el día y la hora. Solo me falta saber qué servicio quieres.
```

Si el número entra por WhatsApp y no existe todavía en la base, el sistema usa ese número como contacto y sigue el flujo normal sin volver a pedir teléfono.

Si el cliente dice solo `este viernes por la tarde`, el bot resuelve la fecha y conserva la franja, pero pide una hora concreta antes de crear la cita.

Alta manual rápida:

```text
Agenda -> Nueva cita
Ficha de cliente -> Nueva cita para este cliente
```

La cita manual sale `confirmada` por defecto y ahora comprueba capacidad básica por categoría y solape por duración.
En nueva/editar cita tienes también un calendario visual y atajos como `Hoy`, `Mañana`, `+7 días` y `+20 días` para poner la fecha con un clic.
Además, al crear una cita sin cliente fijado puedes localizar a la clienta con una búsqueda rápida por nombre o teléfono. El listado prioriza coincidencias más cercanas y enseña solo un bloque corto de resultados para que el flujo siga ágil aunque haya más fichas.

Edición rápida:

```text
Agenda -> Editar
Ficha de cliente -> Editar
```

Puedes cambiar servicio, fecha, hora, estado y notas. La edición vuelve al punto desde el que entraste y mantiene la comprobación básica de disponibilidad.
También tienes atajos rápidos de recolocación como `Mañana`, `+7 días`, `+30 min` y `+1 h`.

Reprogramación rápida desde agenda:

```text
Agenda -> +30 min | +1 h | Mañana | +7 días
Agenda visual -> Atención ahora / Siguiente cita -> +30 min | +1 h | Mañana | +7 días
```

Estos atajos mueven la cita sin pasar por la edición completa, pero siguen usando la misma validación de disponibilidad. Si el nuevo hueco no encaja, la cita no se toca y la agenda muestra el motivo.

Repetir cita de una clienta habitual:

```text
Ficha de cliente -> Historial de citas -> Repetir
```

Ese acceso reutiliza cliente, servicio y hora, deja esa referencia visible en el formulario y además propone una fecha rápida razonable con reglas simples:

- `uñas` -> `+20 días`
- `color` -> `+28 días`
- `corte/peinado` -> `+30 días`

Además deja atajos visibles para `+20 días`, `+28 días` y `+30 días`, de forma que se pueda ajustar sin rehacer la cita.

Filtros rápidos en agenda:

```text
Todas | Hoy | Pendientes | Confirmadas | Completadas | Canceladas
```

Búsqueda rápida en agenda:

```text
Buscar cliente, teléfono o servicio
```

La búsqueda actúa dentro del filtro visible de la agenda, sin cambiar de pantalla.

Operativa diaria en agenda:

- bloque `Atención ahora` con pendientes de la fecha visible
- bloque `Siguiente cita` con acceso rápido a editar, confirmar o abrir cliente
- bloque `Acciones rápidas` para nueva cita, pendientes, hoy y cambio de vista

Vista mensual simple:

```text
Agenda -> calendario mensual -> clic en un día -> agenda filtrada a esa fecha
```

La vista mensual muestra la carga por día dentro del filtro actual y deja abrir `Nueva cita` con esa fecha ya puesta.

Agenda visual:

```text
/agenda/visual
```

Muestra:

- horas visibles
- tres días cercanos en columnas
- citas como bloques dentro del horario
- acceso directo a editar cada cita

La vista lista sigue siendo mejor para revisar muchas citas seguidas o cambiar estados en bloque.
La vista visual está pensada para leer la jornada de un vistazo y detectar huecos más rápido.

Edición simple de cliente:

```text
Ficha de cliente -> Editar cliente
```

Puedes corregir:

- nombre
- teléfono
- email
- notas

Control simple de duplicados:

- el teléfono es la referencia principal del cliente
- se normaliza quitando espacios, guiones y formatos parecidos
- `+34 600 123 123` y `600123123` se tratan como el mismo teléfono
- si el teléfono ya existe, el sistema reutiliza esa ficha o bloquea la edición para evitar duplicados básicos

Servicios:

```text
Servicios -> Nuevo servicio
Servicios -> Editar
Servicios -> Activar / Desactivar
```

Cada servicio permite cambiar:

- nombre
- categoría
- duración estimada
- precio orientativo
- estado activo

Los servicios activos alimentan el chat y las nuevas citas. Si un servicio está inactivo, deja de ofrecerse de forma normal.

Personal y capacidad:

```text
Personal -> Nueva persona
Personal -> Editar
Personal -> Guardar capacidad
```

Puedes configurar:

- nombre
- rol opcional
- categorías que puede atender
- estado activo
- capacidad orientativa por categoría

Disponibilidad básica actual:

- usa la duración del servicio
- mira la categoría del servicio
- cuenta citas activas que se solapan en esa franja
- respeta la capacidad efectiva de la categoría
- bloquea una categoría si no hay personal activo para atenderla

Eso permite, por ejemplo, que peluquería y uñas convivan a la misma hora si hay capacidad, bloquea una tercera coloración si la categoría ya está llena y evita aceptar una manicura si no hay nadie activo en uñas.

La agenda interna prioriza hoy y próximas citas; el histórico pasado sigue visible, pero ya no se coloca antes que lo inmediato.

Cuando una franja está ocupada, el chat y la cita manual muestran alternativas cercanas del mismo día o del siguiente día abierto, por ejemplo `11:30`, `11:45`, `12:00` o `2026-04-20 10:00`, para resolver la reserva con menos ida y vuelta.

También se ha pulido el tono del chat para que suene menos repetitivo y más de negocio real, sin perder claridad.
Además, si el chat acaba de ofrecer reservar, ya entiende mejor respuestas como `sí, soy Ana` o `mechas mañana por la tarde` sin obligar a repetir el contexto desde cero.

Dirección visual actual del panel:

- base clara y cálida, con blanco roto y crema suave
- acentos rosa empolvado, nude y ciruela suave
- degradados ligeros solo en cabeceras, botones principales y bloques clave
- prioridad a contraste, lectura rápida y acciones visibles

## Personalizar el negocio

Edita directamente desde interfaz:

```text
/config/negocio
/servicios
/personal
/clientes/{id}/editar
/config/canales/whatsapp
```

En `/config/negocio` ya puedes cambiar:

- nombre del negocio
- logo del negocio
- sector
- teléfono principal
- dirección
- resumen de horarios
- horario de lunes a viernes
- horario de sábado
- horario de domingo
- saludo base del chat
- mensaje base cuando no entiende algo

Eso se guarda en SQLite como configuración editable y se aplica encima de la base del proyecto.

El logo se guarda como archivo local en `demo/data/uploads/branding/` y la app conserva solo su ruta en la configuración editable de SQLite.

Desde esa misma pantalla puedes:

- ver el logo actual
- subir uno nuevo
- sustituirlo
- quitarlo si hace falta

El logo admite PNG, JPG/JPEG o WEBP y el límite visible actual es de 5 MB.

En `/config/acceso` ya puedes:

- ver el usuario admin actual
- cambiar el usuario admin
- cambiar la contraseña del panel
- confirmar la nueva contraseña
- exigir la contraseña actual antes de guardar

Ahí no entran secretos técnicos de sesión ni nombre de cookie.

En `/config/usuarios` ya puedes:

- crear usuarios internos
- elegir rol `admin` o `staff`
- activar o desactivar accesos
- cambiar contraseña sin mostrar la actual

`staff` entra a agenda, clientas y citas. `admin` mantiene acceso completo, incluida la configuración.
La protección ya no depende tanto de prefijos globales: las rutas internas principales declaran directamente si piden acceso operativo o admin.

Blindajes básicos actuales:

- el username del acceso bootstrap actual queda reservado y no se puede reutilizar como usuario interno
- no se puede degradar o desactivar el último admin interno activo desde panel
- si todavía no existe ningún admin interno activo, el siguiente usuario interno debe crearse como `admin` activo

`demo/data/negocio.json` sigue siendo útil para lo que todavía conviene mantener como base de arranque:

```text
demo/data/negocio.json
```

Ahí siguen viviendo la estructura inicial de la demo, servicios, categorías, datos semilla y la configuración simple de auth si no usas variables de entorno.

## Más detalle

La explicación funcional está en `docs/DEMO_WEB.md`.
La separación entre núcleo operativo, configuración y capa inteligente está en `docs/ARQUITECTURA_FUNCIONAL.md`.
Los principios de uso diario y sencillez están en `docs/USABILIDAD_Y_SENCILLEZ.md`.
La dirección visual actual está en `docs/ESTILO_VISUAL.md`.
La estrategia de selección de servicios está en `docs/SELECCION_SERVICIOS.md`.
La configuración de canales y WhatsApp está en `docs/CANALES_Y_WHATSAPP.md`.
