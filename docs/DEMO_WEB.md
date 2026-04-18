# Demo web con clientes, citas y agenda

La arquitectura funcional del sistema está documentada en `docs/ARQUITECTURA_FUNCIONAL.md`.
La configuración de canales está documentada en `docs/CANALES_Y_WHATSAPP.md`.

## Qué cambia en esta versión

La demo deja de depender de un JSON de leads y pasa a usar SQLite como fuente principal para datos operativos.

Ahora el sistema:

- Responde preguntas frecuentes.
- Mantiene el chat público en `/`.
- Protege el panel interno con login simple y sesión por cookie.
- Reúne la configuración útil del negocio en un centro simple en `/config`.
- Permite editar datos básicos del negocio desde `/config/negocio`.
- Detecta intención de cita.
- Pide fecha/hora o franja, teléfono, nombre si hace falta y servicio.
- Normaliza fechas a `YYYY-MM-DD`.
- Normaliza horas a `HH:MM`.
- Conserva la franja como apoyo, pero no crea la cita hasta tener hora concreta.
- Busca clientes por teléfono.
- Reutiliza el nombre si el cliente ya existe.
- Si el mensaje entra por WhatsApp con número conocido, reconoce automáticamente a la clienta y reutiliza su ficha sin volver a pedir teléfono.
- Crea clientes nuevos cuando el teléfono no existe.
- Registra citas asociadas a clientes.
- Guarda una referencia estable al servicio para no romper histórico ni disponibilidad al renombrarlo.
- Permite crear citas manualmente desde agenda o desde ficha de cliente.
- Permite editar citas existentes de forma rápida.
- Permite repetir una cita desde la ficha del cliente reutilizando servicio y hora.
- Muestra agenda interna.
- Añade una vista agenda visual inspirada en agenda de papel.
- Refuerza la agenda como herramienta diaria con bloques de atención, siguiente cita y acciones rápidas.
- Permite cambiar estado de una cita.
- Muestra lista de clientes y ficha con historial básico.
- Si una hora no está disponible, propone huecos cercanos del mismo día o del siguiente día abierto cuando puede calcularlos.
- Si el cliente ya había indicado una franja como `mañana`, `tarde` o `noche`, intenta respetarla antes de sugerir horas fuera de esa preferencia.
- Aprovecha mejor datos dados fuera de orden durante la reserva.
- Cuando solo falta un dato, pregunta solo por eso con una respuesta más corta.

Además, la estructura interna queda algo más ordenada sin cambiar comportamiento:

- `demo/app.py` mantiene el wiring principal y las rutas.
- `demo/web/context.py` agrupa auth simple, carga de negocio y estado web reutilizable.
- `demo/web/view_helpers.py` agrupa helpers de agenda, calendario y formularios.
- `demo/core/bot_logic.py` sigue orquestando el chat, pero parte del peso se reparte en:
  - `demo/core/chat_booking.py`
  - `demo/core/chat_state.py`
  - `demo/core/chat_text.py`
  - `demo/core/chat_channels.py`

## Estructura de datos

Base local:

```text
demo/data/negocio.db
```

Tabla `clientes`:

- `id`
- `nombre`
- `telefono` único
- `email`
- `notas`
- `fecha_alta`
- `ultima_visita`

Tabla `citas`:

- `id`
- `cliente_id`
- `fecha`
- `hora`
- `franja`
- `servicio_id`
- `servicio`
- `estado`
- `notas`
- `created_at`

Estados de cita:

- `pendiente`
- `confirmada`
- `completada`
- `cancelada`

Cuando una cita pasa a `completada`, se actualiza `ultima_visita` del cliente con la fecha de esa cita.

## Normalización de fecha y hora

La agenda trabaja con:

```text
fecha = YYYY-MM-DD
hora  = HH:MM
```

Expresiones de fecha soportadas:

- `hoy`
- `mañana`
- `pasado mañana`
- días de la semana: `lunes`, `martes`, `miércoles`, `jueves`, `viernes`, `sábado`, `domingo`
- `este viernes`, `este lunes`
- `próximo viernes`, `próximo lunes`
- fechas explícitas: `18/04`, `18-04-2026`, `2026-04-18`, `18 de abril`

Reglas usadas:

- `mañana` y `pasado mañana` se calculan con la fecha actual del sistema y la zona horaria del negocio.
- Un día suelto como `viernes` se interpreta como el próximo viernes no pasado.
- `este viernes` se interpreta dentro de la semana actual; si ese día ya pasó, el bot pide precisión.
- `próximo viernes` apunta al siguiente viernes razonable después de esta semana cuando aplica.
- Una fecha explícita sin año usa el año actual; si ya pasó, usa el siguiente año.
- Una fecha explícita pasada con año se rechaza y el bot pide otra fecha.

Expresiones de hora soportadas:

- `10`
- `10:00`
- `17`
- `17:30`
- `a las 9`
- `a las 09:15`
- `sobre las 18`
- `sobre las 17:30`

Franjas soportadas:

- `por la mañana`
- `por la tarde`
- `por la noche`
- `mediodía`

Las franjas se guardan en `franja`, pero no sustituyen a `hora`. Si el usuario dice `este viernes por la tarde`, el bot responde con la fecha normalizada y pide una hora aproximada antes de crear la cita.

## Cómo se ejecuta

Desde Windows PowerShell:

```powershell
cd H:\servicio_ia_negocios
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn demo.app:app --reload
```

Desde WSL/Linux:

```bash
cd /mnt/h/servicio_ia_negocios
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn demo.app:app --reload
```

Después abre:

```text
http://127.0.0.1:8000
```

## Cómo se ejecutan los tests

Windows PowerShell:

```powershell
cd H:\servicio_ia_negocios
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

WSL/Linux:

```bash
cd /mnt/h/servicio_ia_negocios
.venv/bin/python -m unittest discover -s tests -v
```

Cobertura actual de la suite mínima:

- normalización de teléfono
- reutilización de cliente por teléfono
- login, logout y protección básica del panel interno
- parsing básico de fecha/hora
- matching de servicios
- aclaraciones cortas del chat
- creación simple de cita
- validación básica de solape/capacidad
- servicio central de creación y edición de citas
- alta manual de cita desde `/citas/nueva`
- edición manual de cita desde `/citas/{id}/editar`
- atajos de mostrador: filtrar cliente en alta manual, repetir cita y recolocar con desplazamientos rápidos

## Núcleo de citas centralizado

La creación y edición de citas pasan ahora por `demo/core/appointment_service.py`, que centraliza:

- validación básica de fecha, hora y estado
- resolución del servicio real
- comprobación de disponibilidad
- escritura final de la cita

Límite actual:

- sigue siendo una app SQLite pequeña, no un motor complejo de reservas concurrentes
- la lógica queda mucho menos dispersa, pero todavía no resuelve asignación avanzada de trabajadora o recursos

## Qué sigue sin cubrirse todavía

La red de seguridad ya protege mejor lo delicado, pero todavía quedan huecos razonables:

- render visual fino de plantillas
- agenda visual como experiencia completa
- configuración del negocio y canales con más detalle
- flujo completo de WhatsApp simulado con `incoming_phone`

## Cómo se inicializa la base

No hay comando manual. Al importar la app, `demo/app.py` llama a `init_db()` y crea `demo/data/negocio.db` si no existe.

Para resetear la demo:

Windows PowerShell:

```powershell
Remove-Item demo\data\negocio.db
.\.venv\Scripts\python.exe -m uvicorn demo.app:app --reload
```

WSL/Linux:

```bash
rm demo/data/negocio.db
.venv/bin/python -m uvicorn demo.app:app --reload
```

La base se volverá a crear vacía.

## Rutas disponibles

```text
/                 chat de cliente
/login            acceso al panel interno
/logout           cierre de sesión
/agenda           agenda de citas
/agenda/visual    agenda visual tipo planning
/citas/nueva      alta manual rápida de cita
/citas/{id}/editar edición simple de cita
/clientes         listado de clientes
/clientes/{id}    ficha de cliente con historial
/config           centro de configuración
/config/negocio   datos básicos del negocio
/config/canales   redirección al centro de configuración
/config/canales/whatsapp configuración rápida de WhatsApp
/health           estado técnico
```

## Autenticación simple

La demo protege las rutas internas del panel:

- `/agenda`
- `/agenda/visual`
- `/clientes...`
- `/citas...`
- `/servicios...`
- `/personal...`
- `/config...`

Si entras sin sesión, la app te lleva a `/login` y, al entrar bien, vuelve al punto útil.

Configuración base en `demo/data/negocio.json`:

```json
"auth": {
  "admin_username": "admin",
  "admin_password": "nova-demo-2026",
  "session_secret": "nova-panel-session-secret-2026",
  "session_cookie": "nova_panel_session"
}
```

También admite estas variables de entorno:

- `APP_ADMIN_USERNAME`
- `APP_ADMIN_PASSWORD`
- `APP_SESSION_SECRET`
- `APP_SESSION_COOKIE`

Limitaciones de esta fase:

- solo hay una cuenta admin
- la contraseña se configura en JSON o variables de entorno, sin hashing propio
- no hay roles ni permisos avanzados
- no hay recuperación de contraseña
- no hay protección CSRF dedicada para logout o formularios internos

## Contexto de WhatsApp

La demo no necesita todavía una integración real con Meta para aprovechar el número entrante.

La API de chat acepta dos datos opcionales:

- `channel`
- `incoming_phone`

En la demo web puedes simularlo abriendo:

```text
/?channel=whatsapp&incoming_phone=600111222
```

Comportamiento:

- si el teléfono ya existe, la conversación se asocia a esa ficha
- el bot saluda por nombre de forma breve y natural
- no vuelve a pedir teléfono durante la reserva
- si el teléfono no existe, usa igualmente ese número como contacto y solo pide nombre cuando haga falta

Si la persona corrige su nombre de forma explícita, el sistema continúa con prudencia y evita respuestas demasiado confiadas.

## Configuración básica del negocio

Desde `/config/negocio` ya puedes editar:

- nombre del negocio
- sector
- teléfono principal
- dirección
- resumen de horarios
- horario de lunes a viernes
- horario de sábado
- horario de domingo
- saludo base del chat
- mensaje base cuando el chat no entiende algo

Eso se guarda en SQLite como configuración editable del negocio.

Sigue fuera de esta pantalla:

- servicios
- personal
- canales
- estructura base de la demo
- configuración simple de auth

Esas piezas siguen viviendo en sus pantallas propias o en `demo/data/negocio.json` cuando actúa como base de arranque.

## Selección de servicios

La demo compara el mensaje del usuario con los servicios configurados en `negocio.json`.

Ahora tiene en cuenta:

- intención principal: corte, color, mechas, uñas, barba, etc.
- modificadores: caballero/hombre, mujer, infantil/niño/niña
- alias específicos configurados por servicio
- conflictos entre modificadores

Si el usuario dice `soy hombre`, no debe responder con `Corte mujer`.

Si el usuario dice solo `quiero un corte` y hay varias variantes, pide aclaración.

El detalle está en `docs/SELECCION_SERVICIOS.md`.

## Creación manual de citas

La demo ya no depende solo del chat para registrar citas.

Puntos de entrada:

- `Agenda -> Nueva cita`
- `Ficha de cliente -> Nueva cita para este cliente`

Uso desde agenda:

- puedes elegir un cliente existente
- o dar de alta un cliente básico rápido con nombre y teléfono
- eliges servicio, fecha, hora, estado inicial y notas opcionales

Uso desde ficha:

- el cliente ya va preseleccionado
- solo tienes que indicar servicio, fecha, hora y guardar

La cita manual sale `confirmada` por defecto porque la está registrando el negocio directamente.

## Agenda visual

La demo tiene dos formas de leer la agenda:

### Vista lista

Ruta:

```text
/agenda
```

Mejor para:

- revisar muchas citas seguidas
- buscar rápido
- cambiar estados en bloque
- trabajar con lógica más tabular

### Vista visual

Ruta:

```text
/agenda/visual
```

Mejor para:

- entender el día de un vistazo
- ver horas y huecos como en una agenda de trabajo
- detectar carga rápida de la jornada
- entrar a editar una cita desde su bloque

La vista visual:

- muestra un planning por horas
- enseña varios días cercanos en columnas
- coloca cada cita como bloque según su hora
- mantiene filtros rápidos
- mantiene acceso a `Nueva cita`

Limitaciones actuales:

- no hay drag & drop
- no es una agenda semanal compleja
- la planificación depende de la duración estimada del servicio
- está optimizada primero para escritorio

La comprobación básica de disponibilidad sigue activa: revisa solape por duración, categoría y capacidad activa antes de guardar.

Si la hora pedida no encaja pero encuentra huecos útiles, el sistema propone alternativas cortas para ahorrar ida y vuelta. Por ejemplo:

```text
No puedo confirmar esa hora... Te puedo proponer 11:30, 11:45, 12:00.
```

Y si ese día está cerrado o no cabe dentro del horario, puede saltar al siguiente día abierto:

```text
No puedo confirmar esa cita porque el 2026-04-19 estamos cerrados. Te puedo proponer 2026-04-20 10:00, 2026-04-20 10:15, 2026-04-20 09:45.
```

## Edición simple de citas

La cita ya creada puede corregirse sin rehacerla completa.

Puntos de entrada:

- botón `Editar` en agenda
- botón `Editar` en el historial de la ficha del cliente

Campos editables:

- servicio
- fecha
- hora
- estado
- notas

El cliente queda fijado en esta fase para que la corrección sea rápida y sin errores.

La edición:

- carga los datos actuales
- valida fecha y hora
- mantiene la comprobación básica de disponibilidad
- vuelve al punto de origen con confirmación visual

## Filtros rápidos en agenda

La agenda admite filtros simples por query param:

```text
/agenda?filtro=hoy
/agenda?filtro=pendientes
/agenda?filtro=confirmadas
/agenda?filtro=completadas
/agenda?filtro=canceladas
```

En interfaz aparecen como accesos rápidos:

- Todas
- Hoy
- Pendientes
- Confirmadas
- Completadas
- Canceladas

No hay búsqueda avanzada ni filtros complejos en esta fase. La idea es reducir escaneo visual, no convertir la agenda en un panel pesado.

Además, la agenda tiene una búsqueda rápida local por:

- cliente
- teléfono
- servicio

Esa búsqueda actúa dentro del filtro actual y no obliga a recargar otra pantalla.

## Vista mensual simple en agenda

La agenda incorpora una vista mensual compacta encima de la tabla principal.

Sirve para:

- ver qué días tienen más carga
- entrar a una fecha concreta con un clic
- abrir una nueva cita con esa fecha ya preseleccionada

Comportamiento:

- respeta el filtro actual de agenda
- muestra cuántas citas hay por día dentro de ese filtro
- al pulsar un día, la agenda pasa a mostrar solo esa fecha
- desde ahí, `Nueva cita` abre con esa fecha ya puesta

No sustituye la tabla diaria. La complementa para reducir búsqueda visual y moverse más rápido por semanas cargadas.

## Gestión simple de servicios

La demo incorpora una pantalla propia de `Servicios`.

Permite:

- ver el listado
- crear un servicio
- editarlo
- activarlo o desactivarlo

Campos mínimos actuales:

- nombre
- categoría
- duración estimada en minutos
- precio orientativo
- activo o no

Integración actual:

- los servicios activos alimentan el chat
- los servicios activos aparecen en nuevas citas
- si se desactiva un servicio, deja de ofrecerse de forma normal
- una cita antigua con un servicio inactivo se puede seguir editando sin perder esa referencia

## Gestión simple de personal y capacidad

La demo incorpora una pantalla propia de `Personal`.

Permite:

- crear o editar una persona
- marcar si está activa
- marcar qué categorías puede atender
- ajustar una capacidad orientativa por categoría

Campos mínimos por persona:

- nombre
- rol opcional
- categorías
- activo o no

Integración actual:

- el personal queda configurado en SQLite, no en un supuesto fijo
- la capacidad por categoría queda guardada y visible
- ya se usa como base de disponibilidad simple por categoría y solape
- todavía no se usa para asignación automática ni para motor avanzado completo

Objetivo real de esta fase:

- dejar de depender de datos fijos en archivo para servicios y personal
- preparar una disponibilidad más real sin meter complejidad antes de tiempo

## Disponibilidad básica por categoría

La demo ya no trabaja solo con “misma fecha y misma hora”.

Ahora, al crear o editar una cita:

- toma la duración del servicio
- identifica su categoría
- revisa cuántas citas activas de esa categoría se solapan en esa franja
- compara ese solape con la capacidad efectiva de la categoría

La capacidad efectiva se apoya en:

- capacidad configurada por categoría
- personal activo que puede atender esa categoría

Ejemplo práctico:

- peluquería puede permitir varias citas a la vez si tiene capacidad
- uñas puede convivir con peluquería a la misma hora
- coloración larga puede bloquear una tercera cita solapada si esa categoría ya está llena

Lo que no hace aún:

- asignar la cita a una persona concreta
- calcular agendas individuales
- proponer huecos alternativos automáticos

## Edición simple de cliente

Cada ficha de cliente incorpora un acceso visible a `Editar cliente`.

Campos editables:

- nombre
- teléfono
- email
- notas

Objetivo:

- corregir altas rápidas hechas deprisa
- completar una ficha básica sin salir del flujo
- mantener las citas ya asociadas sin tocarlas

Al guardar:

- vuelve a la ficha del cliente
- muestra confirmación breve
- no cambia las citas existentes

## Control simple de duplicados

La ficha de cliente usa el teléfono como referencia principal.

Reglas aplicadas:

- antes de crear un cliente nuevo, se busca si ya existe ese teléfono
- en edición, no se permite guardar el teléfono si ya pertenece a otro cliente
- el teléfono se normaliza antes de comparar

Normalización aplicada:

- quita espacios
- quita guiones y símbolos
- tolera variantes como `+34` o `0034` para números españoles habituales

Ejemplos:

```text
600 123 123
+34 600 123 123
0034-600-123-123
```

Se consideran la misma ficha si el número base coincide.

En alta rápida desde `Nueva cita`, si el teléfono ya existe, el sistema reutiliza esa ficha para evitar duplicados tontos.

## Aclaración conversacional corta

Cuando el bot pregunta por una aclaración de servicio, guarda un contexto breve de la última pregunta.

Ejemplos:

```text
Usuario: quiero un corte
Bot: ¿Te refieres a Corte caballero, Corte mujer o Corte infantil?
Usuario: hombre
Bot: Sí, trabajamos ese servicio. Corte caballero...
```

```text
Usuario: quiero uñas
Bot: ¿Te refieres a Manicura, Uñas gel o Pedicura?
Usuario: gel
Bot: Sí, trabajamos ese servicio. Uñas gel...
```

Reglas:

- solo recuerda la última aclaración de servicio
- dura pocos turnos
- si la respuesta breve encaja, resuelve sin reiniciar
- si no encaja, vuelve al flujo general sin bloquear la conversación

## Continuidad práctica del chat

Además de la aclaración corta, el chat mantiene ahora una memoria breve para ofertas de reserva.

Ejemplos:

```text
Usuario: precio del tinte
Bot: Precio orientativo... Si quieres, te dejo ya una solicitud de cita.
Usuario: sí
Bot: ¿Qué día y hora te vendría bien?
```

```text
Usuario: necesito mechas
Bot: Sí, trabajamos ese servicio... ¿Quieres que registre una solicitud de cita?
Usuario: sí, mañana a las 17
Bot: ¿Qué teléfono de contacto dejamos?
```

También entra ya directamente en modo cita cuando el mensaje trae una intención operativa clara, por ejemplo:

```text
mañana a las 17 mechas
```

Eso evita pasos de más y hace el chat más natural sin depender de una IA externa.

Además, la captura de datos es ahora más oportunista:

- en cada mensaje intenta aprovechar teléfono, nombre, fecha, hora y servicio si aparecen
- si el usuario da nombre o teléfono antes de tiempo, no se pierden
- si el bot acaba de ofrecer una reserva, entiende mejor respuestas afirmativas con datos mezclados como `sí, soy Ana`
- también puede continuar desde una señal útil como `mechas mañana por la tarde` sin obligar a rehacer toda la frase
- después pide solo el dato que realmente sigue faltando

Ejemplo:

```text
Bot: ¿A qué hora lo dejamos?
Usuario: Ana
Bot: Perfecto, ya tengo el nombre. Te lo preparo para 2026-04-18. ¿A qué hora lo dejamos?
```

Y si ya solo falta un dato, responde más corto:

```text
Perfecto. Solo me falta la hora.
```

También se ha reducido la repetición de frases para que el tono sea más natural y menos de plantilla.

Para no arrastrar contexto viejo, esa memoria corta caduca tras un rato de inactividad. Así un `sí` de una conversación anterior no reabre una reserva cuando el usuario ha vuelto más tarde a preguntar otra cosa.

## Comprobación básica de agenda

La demo no asigna todavía la cita a una persona concreta, pero ya hace una comprobación operativa más seria:

- usa la duración del servicio
- mira la categoría del servicio
- cuenta citas activas que se solapan en esa franja
- respeta la capacidad efectiva de la categoría
- bloquea una categoría si no hay personal activo para atenderla
- propone horas cercanas del mismo día o del siguiente día abierto dentro del horario configurado cuando encuentra hueco
- prioriza la franja pedida por el cliente cuando esa preferencia ya está en la conversación

Si el usuario pide una franja amplia como `por la tarde`, no se crea todavía la cita. El bot pide hora concreta.

## Limitaciones actuales

- No hay autenticación.
- No hay multiempresa.
- No hay WhatsApp real.
- No hay Google Calendar.
- No hay asignación automática a una persona concreta.
- No hay borrado de citas.
- No interpreta frases vagas como `cuando puedas`, `un día de estos` o `la próxima semana` sin día concreto.
- No convierte todavía todas las variantes posibles del español coloquial.
- No mantiene una memoria larga; sigue usando solo contexto corto y útil.

La versión está pensada para demo local y validación comercial, no para producción.
