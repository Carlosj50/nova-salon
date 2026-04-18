# Arquitectura funcional

## Qué es este sistema

Este proyecto es una base local para gestión operativa de negocios pequeños: empieza con peluquería/estética, pero no debe quedar atado a ese nicho.

El sistema combina:

- gestión estructurada de clientes y citas
- configuración editable del negocio
- una capa inteligente prudente para interpretar mensajes y guiar el flujo

No es solo una agenda. No es solo un chatbot. No es una demo decorativa de IA.

## Qué no es

- No es un ERP completo.
- No es multiempresa todavía.
- No tiene WhatsApp real todavía.
- No usa modelos externos de IA todavía.
- No debe inventar disponibilidad si no está calculada con datos reales.
- No debe esconder reglas de negocio dentro de textos hardcodeados.

## Las 3 capas

### 1. Núcleo operativo

Es lo estable del sistema. Debe existir aunque cambie el tipo de negocio.

Responsabilidades:

- persistencia SQLite
- clientes
- citas
- agenda
- estados de cita
- lectura/escritura de datos estructurados
- comprobaciones operativas básicas
- reglas generales de disponibilidad

Archivos actuales:

```text
demo/core/db.py
demo/core/models.py
demo/core/repositories.py
demo/core/availability.py
demo/templates/agenda.html
demo/templates/clientes.html
demo/templates/cliente_detalle.html
```

Estado actual:

- `clientes` implementado.
- `citas` implementado.
- agenda HTML implementada.
- estados básicos implementados.
- disponibilidad básica implementada: usa duración, categoría y capacidad simple para evitar solapes que ya no caben.

Lo que no debe vivir aquí:

- nombres de servicios concretos
- duración específica de un servicio concreto
- cuántas trabajadoras tiene una peluquería concreta
- textos comerciales o respuestas conversacionales
- reglas específicas de un negocio particular

### 2. Configuración del negocio

Es lo que cambia entre negocios. Debe poder editarse sin tocar la lógica central.

Base actual:

```text
demo/data/negocio.json
demo/data/negocio.db
```

`negocio.json` sigue guardando:

- nombre del negocio
- sector
- zona horaria
- teléfono
- dirección
- horarios
- mensajes configurables

SQLite guarda ya la configuración operativa editable:

- categorías de servicio
- servicios
- duración orientativa por servicio
- precios orientativos
- alias de búsqueda por servicio
- personal/trabajadoras
- categorías que puede realizar cada persona
- capacidad por categoría
- canales de entrada/salida configurables

Entidades configuradas actualmente:

```text
Negocio
Categorías de servicio
Servicios
Personal / trabajadoras
Reglas operativas
Mensajes del asistente
Canales
```

Decisión importante:

La configuración ya incluye datos que el motor avanzado de disponibilidad necesitará después, aunque la versión actual todavía no los use todos.

Ejemplos:

- `duration_minutes`
- `category`
- `service_categories`
- `staff`
- `category_capacity`
- `operational_buffer_staff`

Esto permite crecer sin reescribir el núcleo.

Decisión actual:

- la identidad general del negocio sigue en JSON
- la configuración operativa viva ya se guarda en SQLite

La configuración de canales se guarda en SQLite porque contiene estado editable desde panel. WhatsApp es el primer canal implementado como configuración, no como integración real.

### 3. Capa inteligente

Es la capa que interpreta lenguaje natural y decide qué pedir después.

Responsabilidades:

- detectar intención
- identificar servicios mencionados
- interpretar fecha/hora/franja
- pedir solo los datos que faltan
- reconocer clientes existentes por teléfono
- reutilizar datos ya conocidos
- no inventar disponibilidad
- consultar núcleo y configuración antes de responder

Archivos actuales:

```text
demo/core/bot_logic.py
demo/core/chat_booking.py
demo/core/chat_state.py
demo/core/chat_text.py
demo/core/chat_channels.py
demo/core/datetime_parser.py
demo/core/service_catalog.py
```

Estado actual:

- interpreta FAQs básicas
- detecta intención de cita
- extrae teléfono, nombre y servicio
- normaliza fecha a `YYYY-MM-DD`
- normaliza hora a `HH:MM`
- conserva franja sin usarla como hora final
- pide precisión cuando falta fecha/hora concreta
- reutiliza cliente existente por teléfono
- consulta disponibilidad básica antes de crear cita

Decisión de mantenimiento:

- `bot_logic.py` sigue siendo el punto de entrada del chat, pero ya no carga solo con todo el peso.
- `chat_booking.py` concentra el flujo de captura y cierre de cita.
- `chat_state.py` concentra estado y utilidades de contexto corto.
- `chat_text.py` separa parsing e intención básica.
- `chat_channels.py` separa el comportamiento específico del canal, como WhatsApp y número entrante.

Lo que no debe hacer:

- inventar huecos disponibles
- asumir capacidad si no está calculada
- decidir reglas específicas que pertenecen a `negocio.json`
- guardar texto ambiguo como fecha/hora principal

## Soporte web

La app web sigue entrando por `demo/app.py`, pero el soporte transversal ya se separa en módulos más pequeños:

```text
demo/app.py
demo/web/context.py
demo/web/view_helpers.py
```

Responsabilidades:

- `app.py`: wiring de FastAPI y rutas.
- `web/context.py`: carga de negocio, auth simple, sesión web y estado corto del chat.
- `web/view_helpers.py`: helpers de agenda, formularios, calendario mensual y planning visual.

La idea no es crear una arquitectura grande, sino bajar radio de impacto y facilitar cambios futuros sin tocar rutas y helpers en el mismo bloque.

## Entidades del sistema

### Negocio

Configurado en `negocio.json`.

Incluye identidad, datos de contacto, horario, zona horaria y mensajes configurables.

### Personal / trabajadoras

Persistido en SQLite, tabla `personal`, con relación a categorías mediante `personal_categorias`.

Cada persona tiene:

- `id`
- `name`
- `role`
- `service_categories`
- `active`

Todavía no se asignan citas a trabajadoras concretas. Queda preparado para la siguiente fase.

### Categorías de servicio

Persistidas en SQLite, tabla `service_categories`.

Sirven para agrupar servicios y calcular disponibilidad por capacidad o personal.

Ejemplos:

- corte y peinado
- coloración
- uñas

### Servicios

Persistidos en SQLite, tabla `servicios_config`.

Cada servicio puede tener:

- `id`
- `name`
- `category`
- `aliases`
- `price`
- `duration`
- `duration_minutes`
- reglas especiales

La capa inteligente usa `aliases`, intención principal y modificadores para detectar servicios en mensajes. El núcleo no debe conocer nombres concretos.

Regla operativa actual:

- solo los servicios activos entran en el chat y en la creación normal de nuevas citas
- los servicios inactivos siguen existiendo como dato histórico o para editar citas antiguas si hace falta

Regla práctica:

- los alias genéricos no deben apuntar a una variante concreta si existen varias variantes
- `corte` no debe pertenecer solo a `Corte mujer`
- `corte hombre`, `corte mujer` y `corte infantil` sí son alias específicos
- si el usuario usa un término genérico y hay varias opciones, la capa inteligente debe pedir aclaración

La estrategia está descrita en `docs/SELECCION_SERVICIOS.md`.

### Clientes

Persistidos en SQLite, tabla `clientes`.

Campos actuales:

- `id`
- `nombre`
- `telefono`
- `email`
- `notas`
- `fecha_alta`
- `ultima_visita`

### Citas

Persistidas en SQLite, tabla `citas`.

Campos actuales:

- `id`
- `cliente_id`
- `fecha`
- `hora`
- `franja`
- `servicio`
- `estado`
- `notas`
- `created_at`

Regla actual:

`fecha` y `hora` deben ser valores normalizados. La franja puede ayudar al negocio, pero no sustituye a la hora.

### Reglas de capacidad / disponibilidad

Ubicación actual:

```text
demo/core/availability.py
demo/data/negocio.json -> operational_rules
```

Implementado ahora:

- duración del servicio
- categoría del servicio
- capacidad efectiva por categoría
- solape básico entre citas activas de la misma categoría

Preparado para después:

- capacidad por categoría
- personal que puede realizar cada categoría
- colchones operativos
- reglas especiales por servicio

### Canales

Persistidos en SQLite, tabla `canales`.

Campos actuales:

- `id`
- `tipo_canal`
- `activo`
- `modo`
- `telefono`
- `nombre_visible`
- `config_json`
- `created_at`
- `updated_at`

WhatsApp es un canal configurable, no una constante del sistema. La configuración vive en `/config/canales/whatsapp`.

La integración real con Meta/Cloud API no está implementada todavía. Queda documentada en `docs/CANALES_Y_WHATSAPP.md`.

## Diseño de disponibilidad

La disponibilidad no debe depender solo de “hay hueco a esa hora”.

Debe terminar dependiendo de:

- fecha y hora normalizadas
- duración del servicio
- categoría del servicio
- personal activo
- qué personal puede realizar ese servicio
- capacidad por categoría
- solapes con citas existentes
- reglas especiales del servicio
- colchones operativos

La versión actual no resuelve todo eso, pero ya usa una base real de categoría, duración y capacidad simple.

## Decisiones tomadas

1. FastAPI se mantiene como capa web simple.
2. SQLite se mantiene como persistencia local.
3. `negocio.json` queda para identidad general del negocio y mensajes, no para cambios operativos del día a día.
4. La lógica de catálogo de servicios sale del bot y queda en `service_catalog.py`.
5. La disponibilidad sale del bot y queda en `availability.py`.
6. La capa inteligente coordina, pero no debe contener reglas particulares del negocio.
7. No se crea cita sin fecha y hora normalizadas.
8. La franja se conserva como información auxiliar.
9. Servicios y personal se gestionan ya desde SQLite y panel HTML simple.
10. La capacidad por categoría queda guardada como configuración real, aunque todavía no decide la disponibilidad final.

## Qué está implementado

- Chat web.
- Agenda HTML.
- Clientes.
- Fichas de cliente.
- Citas.
- Estados de cita.
- Normalización básica de fecha/hora.
- Reutilización de cliente por teléfono.
- Configuración general de negocio.
- Gestión de servicios desde interfaz.
- Gestión de personal desde interfaz.
- Capacidad por categoría guardada en SQLite.
- Configuración de canales con WhatsApp como primer canal.
- Disponibilidad básica por duración, categoría y capacidad simple.

## Qué queda preparado para siguientes fases

### Panel de configuración

Debe permitir editar:

- datos del negocio
- horarios
- servicios
- categorías
- duración
- precios
- personal
- capacidades
- reglas especiales
- canales de contacto y sus estados

La identidad general puede seguir en `negocio.json`, pero la configuración operativa nueva ya debe vivir en SQLite.

### Motor de disponibilidad real

Siguiente evolución natural:

- convertir `servicio` de cita en referencia a `service.id`
- añadir duración real a cada cita
- asignar citas a personal o categoría
- calcular solapes por duración
- respetar capacidad por categoría
- respetar especialidades del personal
- proponer alternativas si no hay hueco

### Capa inteligente más potente

Debe seguir estas reglas:

- usar datos reales del núcleo y configuración
- pedir confirmación cuando haya duda
- no prometer huecos no calculados
- proponer opciones solo si el motor de disponibilidad las devuelve

## Regla de mantenimiento

Antes de añadir una función nueva, decidir a qué capa pertenece:

- Si es estructura estable o persistencia: núcleo operativo.
- Si cambia por negocio: configuración.
- Si interpreta o decide con contexto: capa inteligente.

Si una pieza no encaja claramente, hay que revisar el diseño antes de implementarla.
