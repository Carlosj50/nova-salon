# Guía visual de uso de la app

Esta guía está pensada para explicar la app a una peluquería o centro de belleza de forma clara, breve y realista.

No es una guía técnica. No intenta enseñar cómo está hecho el sistema por dentro. Su objetivo es mostrar, con capturas reales, cómo se usa en el trabajo diario.

## Para quién está pensada

Esta guía encaja especialmente bien para:

- dueña o encargada del salón
- recepción o persona de mostrador
- personal nuevo que necesita ubicarse rápido
- presentaciones comerciales de la app

## Idea principal de la app

La app está pensada para ayudar al negocio a trabajar con menos roce en cuatro tareas principales:

1. ver la agenda del día
2. crear y mover citas con rapidez
3. consultar clientas y su historial
4. mantener una configuración simple del negocio

## Cómo conviene usar esta guía

Cada bloque está pensado para ir acompañado por una captura real de la app.

En cada sección se incluye:

- la captura recomendada
- lo que esa pantalla debe transmitir
- el texto corto que puede ir debajo
- los puntos que conviene explicar al enseñarla

Las capturas sugeridas se guardan en:

```text
docs/capturas/manual/
```

## Índice visual recomendado

1. Acceso al panel
2. Agenda lista como centro de trabajo
3. Agenda visual para leer la jornada
4. Crear una cita manual
5. Buscar una clienta y ver su ficha
6. Repetir una cita habitual
7. Reprogramar una cita con rapidez
8. Confirmar, cancelar o completar una cita
9. Configurar el negocio y su marca
10. Gestionar acceso y usuarios
11. Chat demo y apoyo por WhatsApp

## Preparación recomendada antes de sacar capturas

Antes de hacer las capturas conviene preparar una base visual limpia:

- nombre del negocio ya configurado
- logo subido y visible
- algunas citas de ejemplo en distintos estados
- varias clientas con nombres y teléfonos creíbles
- al menos un usuario `staff`
- agenda con una mezcla razonable de huecos y citas

Evita:

- nombres de prueba tipo `Cliente Test 1`
- teléfonos demasiado artificiales
- textos a medio escribir
- pantallas vacías si la guía quiere enseñar operativa real

## 1. Acceso al panel

**Captura sugerida:** `01-acceso-panel.png`

**Qué debe enseñar esta captura**

El acceso al panel debe transmitir que la app es sencilla de usar y que la parte interna está separada del chat público.

**Texto corto sugerido bajo la captura**

```text
El acceso al panel es directo: usuario, contraseña y entrar.
```

**Qué conviene explicar**

- la pantalla de acceso es simple y no obliga a pasar por pasos técnicos
- `admin` y `staff` usan la misma entrada
- una vez dentro, cada rol ve solo lo que necesita

## 2. Agenda lista como centro de trabajo

**Captura sugerida:** `02-agenda-lista.png`

**Qué debe enseñar esta captura**

La agenda lista es la pantalla principal para trabajar durante el día.

**Texto corto sugerido bajo la captura**

```text
La agenda lista concentra lo importante del día y permite actuar rápido.
```

**Qué conviene explicar**

- resumen del día
- bloques de pendientes y siguiente cita
- acciones rápidas visibles
- lista de citas como herramienta principal de mostrador

**Lo importante al presentarla**

- la hora y la clienta son lo primero que se lee
- el estado se entiende rápido
- las acciones útiles siguen ahí, pero pesan menos visualmente

## 3. Agenda visual para leer la jornada

**Captura sugerida:** `03-agenda-visual.png`

**Qué debe enseñar esta captura**

La agenda visual ayuda a entender la carga horaria y ver huecos de un vistazo.

**Texto corto sugerido bajo la captura**

```text
La vista visual ayuda a leer la jornada y detectar huecos con rapidez.
```

**Qué conviene explicar**

- no sustituye a la agenda lista
- es una vista complementaria
- sirve especialmente para leer el día como planning

**Cuándo tiene más sentido usarla**

- al abrir la jornada
- al buscar huecos
- al revisar carga del día por horas

## 4. Crear una cita manual

**Captura sugerida:** `04-nueva-cita.png`

**Qué debe enseñar esta captura**

La alta manual está pensada para situaciones reales de llamada o mostrador.

**Texto corto sugerido bajo la captura**

```text
Una cita se puede crear sin pasar por el chat y sin perder tiempo.
```

**Qué conviene explicar**

- se puede localizar una clienta existente escribiendo nombre o teléfono
- si no existe, se crea en ese mismo flujo
- la cita se valida antes de guardarse

**Recorrido práctico que conviene contar**

1. localizar clienta
2. elegir servicio
3. fijar fecha y hora
4. guardar

## 5. Buscar una clienta y ver su ficha

**Captura sugerida:** `05-ficha-clienta.png`

**Qué debe enseñar esta captura**

La ficha de clienta es el punto natural para revisar historial y continuar la relación.

**Texto corto sugerido bajo la captura**

```text
La ficha reúne datos útiles, historial y acceso rápido a una nueva cita.
```

**Qué conviene explicar**

- búsqueda por nombre o teléfono
- historial visible
- datos editables
- acceso rápido a `Nueva cita`
- acceso rápido a `Repetir última`

**Caso real que conviene mencionar**

```text
Una clienta termina hoy y quiere dejar ya la siguiente cita apuntada.
```

## 6. Repetir una cita habitual

**Captura sugerida:** `06-repetir-cita.png`

**Qué debe enseñar esta captura**

El sistema ayuda a repetir una cita frecuente sin reconstruirlo todo desde cero.

**Texto corto sugerido bajo la captura**

```text
Repetir última reutiliza clienta, servicio y hora, y propone una fecha razonable.
```

**Qué conviene explicar**

- no es una recurrencia compleja
- no intenta adivinar en exceso
- simplemente acelera un caso real y repetido

**Qué ahorra de verdad**

- menos clics
- menos memoria mental
- menos necesidad de revisar la última cita a mano

## 7. Reprogramar una cita con rapidez

**Captura sugerida:** `07-reprogramar-rapido.png`

**Qué debe enseñar esta captura**

La agenda permite mover una cita común sin tener que entrar siempre en una edición completa.

**Texto corto sugerido bajo la captura**

```text
Mover una cita frecuente puede resolverse en un gesto corto desde la agenda.
```

**Qué conviene explicar**

- atajos rápidos:
  - `+30 min`
  - `+1 h`
  - `Mañana`
  - `+7 días`
- la disponibilidad sigue validándose
- si el hueco no encaja, el cambio no se guarda

**Cuánto conviene recalcar**

Esto ahorra mucho tiempo en cambios pequeños del día a día.

## 8. Confirmar, cancelar o completar una cita

**Captura sugerida:** `02-agenda-lista.png`

**Qué debe enseñar esta captura**

La agenda deja claras las acciones normales por estado sin saturar de opciones.

**Texto corto sugerido bajo la captura**

```text
Cada cita muestra las acciones habituales según su estado actual.
```

**Qué conviene explicar**

- confirmar
- cancelar
- completar
- reabrir una cancelada si hace falta

**Idea a transmitir**

No hace falta pensar entre demasiadas opciones. La pantalla muestra las que tienen sentido en cada caso.

## 9. Configurar el negocio y su marca

**Captura sugerida:** `08-config-negocio.png`

**Qué debe enseñar esta captura**

La app se puede personalizar para que se sienta propia del salón.

**Texto corto sugerido bajo la captura**

```text
Nombre, logo y datos visibles del salón se ajustan desde configuración.
```

**Qué conviene explicar**

- nombre del negocio
- logo
- teléfono
- dirección
- mensaje base del chat

**Lo importante**

La configuración está agrupada, pero no se convierte en un panel pesado.

## 10. Gestionar acceso y usuarios

**Captura sugerida:** `09-config-usuarios.png`

**Qué debe enseñar esta captura**

El acceso interno ya no depende de una sola cuenta para todo.

**Texto corto sugerido bajo la captura**

```text
Admin y staff comparten panel, pero no el mismo nivel de acceso.
```

**Qué conviene explicar**

- `admin` puede gestionar configuración y usuarios
- `staff` entra en la parte operativa diaria
- los usuarios se activan o desactivan
- las contraseñas no se muestran nunca

**Mensaje importante**

Esto cubre una necesidad real del salón sin convertir la app en un sistema de permisos complejo.

## 11. Chat demo y apoyo por WhatsApp

**Captura sugerida:** `10-chat-demo.png`

**Qué debe enseñar esta captura**

El chat no sustituye al panel interno. Actúa como apoyo para:

- resolver preguntas frecuentes
- mostrar servicios y horarios
- recoger una petición de cita

**Texto corto sugerido bajo la captura**

```text
El chat ayuda a responder y captar citas, pero la operativa diaria sigue en agenda y clientas.
```

**Qué conviene explicar**

- resuelve preguntas frecuentes
- ayuda a pedir una cita
- en WhatsApp puede reconocer el teléfono de la clienta si ya existe

**Idea clave**

El chat suma valor sin obligar al negocio a trabajar desde el chat.

## Resumen muy corto para presentar la app en un minuto

Si solo se van a enseñar cuatro capturas, estas serían las mejores:

1. acceso al panel
2. agenda lista
3. nueva cita
4. ficha de clienta con `Repetir última`

Con esas cuatro pantallas ya se entiende casi todo lo importante:

- cómo se entra
- cómo se trabaja
- cómo se crea una cita
- cómo se gestiona una clienta habitual

## Orden recomendado para una demo guiada

Si vas a enseñar la app en directo, este orden suele funcionar bien:

1. acceso
2. agenda
3. nueva cita
4. ficha de clienta
5. repetir cita
6. reprogramar
7. configuración
8. usuarios
9. chat demo

Así la explicación sigue el flujo real de uso del salón.

## Checklist de calidad antes de dar la guía por buena

Antes de cerrar el manual con capturas reales, revisa esto:

- el logo del negocio se ve bien en cabecera
- las fechas y horas visibles tienen sentido
- no hay clientas duplicadas o nombres raros de prueba
- el estado de las citas es creíble
- la agenda no está ni vacía del todo ni artificialmente llena
- la pantalla de configuración no enseña datos sensibles
- la pantalla de usuarios deja clara la diferencia entre `admin` y `staff`

## Lo que esta guía no intenta cubrir

Esta guía no intenta explicar:

- detalles de FastAPI o SQLite
- estructura interna del código
- configuración avanzada por entorno
- arquitectura técnica
- decisiones de desarrollo

Para eso siguen estando:

- [README.md](/mnt/h/servicio_ia_negocios/README.md)
- [docs/DEMO_WEB.md](/mnt/h/servicio_ia_negocios/docs/DEMO_WEB.md)
- [docs/ARQUITECTURA_FUNCIONAL.md](/mnt/h/servicio_ia_negocios/docs/ARQUITECTURA_FUNCIONAL.md)

