# Usabilidad y sencillez operativa

Este sistema no debe convertirse en el centro del negocio. Debe ayudar a una peluquería o centro local a trabajar con menos caos, menos llamadas perdidas y menos pasos.

Regla principal:

```text
El programa no es el negocio. El programa ayuda al negocio.
```

## Problemas detectados

La versión anterior funcionaba, pero tenía fricciones típicas de herramienta que empieza a crecer:

- La agenda era una tabla completa, no una pantalla de trabajo diario.
- Las citas de hoy no estaban destacadas.
- Cambiar estado mostraba demasiadas opciones a la vez.
- La lista de clientes no tenía búsqueda rápida.
- La navegación usaba `Canales`, pero para un negocio local lo importante ahora es `WhatsApp`.
- La configuración de WhatsApp enseñaba campos técnicos al mismo nivel que los campos diarios.
- Había textos correctos técnicamente, pero algo alejados del lenguaje de uso real.
- No había forma rápida de crear una cita manual sin pasar por el chat.
- El chat perdía el contexto cuando pedía una aclaración corta de servicio.
- Corregir una cita exigía demasiado roce porque no había edición directa.
- La agenda necesitaba foco visual para ver solo pendientes o confirmadas sin escanear todo.

## Criterio de diseño

Cada pantalla debe responder a una pregunta práctica.

- Agenda: ¿qué tengo que atender hoy y qué queda pendiente?
- Clientes: ¿cómo encuentro rápido a una persona y veo su historial?
- Servicios: ¿cómo cambio un precio, una duración o desactivo algo sin tocar archivos?
- Personal: ¿quién trabaja y qué categorías puede atender?
- WhatsApp: ¿está visible el número correcto para contactar?
- Chat demo: ¿cómo se ve la atención automática para el cliente?

Si una pantalla no responde a una pregunta práctica, hay que simplificarla, fusionarla o dejarla fuera.

## Cambios aplicados

### Agenda

La agenda pasa a priorizar el día actual.

Ahora muestra:

- resumen de hoy
- citas pendientes
- citas confirmadas
- citas activas
- bloque de citas de hoy
- bloque de próximas y recientes

Las acciones de estado se reducen a las más normales:

- pendiente: confirmar o cancelar
- confirmada: completar o cancelar
- cancelada: reabrir
- completada: sin acción rápida

Esto evita que el negocio tenga que pensar entre cuatro estados cada vez.

Además, incorpora un acceso visible a `Nueva cita`, porque muchas reservas reales se crean en mostrador o por teléfono, no en el chat.

También añade:

- botón `Editar` por cita
- filtros rápidos por estado y por hoy
- vista mensual simple para localizar días cargados
- búsqueda rápida por cliente, teléfono o servicio dentro de agenda
- vista visual tipo planning inspirada en una agenda de papel

Eso reduce el tiempo de corrección y el tiempo de lectura.

La vista visual no sustituye a la lista: la complementa.

Regla práctica:

- si necesitas leer el día como jornada y ver huecos rápido, usa la vista visual
- si necesitas repasar muchas citas o tocar estados en serie, usa la vista lista

### Clientes

La lista de clientes incorpora búsqueda directa por nombre o teléfono en la misma pantalla.

No hay pantalla intermedia ni formulario extra para consultar una ficha.

Flujo esperado:

```text
Clientes -> buscar -> ver ficha
```

Desde la ficha también se puede abrir `Nueva cita para este cliente`, sin volver a elegirlo.

La misma ficha incorpora ahora `Editar cliente`, para corregir nombre, teléfono o notas sin abrir pantallas extra ni entrar en un panel de CRM.

La regla práctica es simple:

- el teléfono manda para evitar duplicados básicos
- si ya existe, se reutiliza la ficha
- si se intenta repetir en edición, se avisa con claridad

### WhatsApp

La navegación interna ahora muestra `WhatsApp` de forma directa.

La pantalla de WhatsApp se centra en:

- activar o desactivar el canal
- número del negocio
- nombre visible
- estado de integración

La referencia técnica queda dentro de un bloque plegable de ajustes futuros.

En la conversación de WhatsApp también se reduce roce:

- si el canal ya trae el número del remitente, no se vuelve a pedir
- si ese número ya existe, se reutiliza la ficha
- si no existe, el flujo solo pide lo que falta de verdad

Eso hace que WhatsApp se sienta más como un canal real y menos como un chat genérico.

### Servicios

La pantalla de servicios está pensada para cambios frecuentes y cortos:

- añadir uno nuevo
- retocar precio o duración
- desactivar un servicio que ya no se ofrece

No hay campos raros ni una ficha técnica larga. Lo importante es que el negocio pueda ajustar la oferta sin tocar JSON.

### Personal

La pantalla de personal no intenta ser un cuadrante complejo.

Resuelve solo lo necesario en esta fase:

- quién forma parte del equipo
- qué categorías puede atender
- si está activa o no
- una capacidad orientativa por categoría

Eso prepara el crecimiento sin meter todavía calendarios individuales ni turnos.

### Navegación

La navegación común queda reducida a:

- Agenda
- Clientes
- Servicios
- Personal
- WhatsApp
- Chat demo

Esto separa mejor el uso interno del negocio y la demo de atención al cliente.

## Principios para siguientes fases

1. La agenda debe seguir siendo la pantalla principal de trabajo.
2. Las tareas frecuentes deben hacerse en una pantalla y con pocos clics.
3. Los estados deben ofrecer acciones naturales, no todas las combinaciones posibles.
4. Los formularios deben pedir solo lo necesario.
5. La configuración técnica debe estar escondida o separada de la operación diaria.
6. El lenguaje debe ser de negocio local, no de sistema informático.
7. No crear una pantalla nueva si una acción puede vivir claramente en una pantalla existente.
8. No añadir paneles avanzados hasta que exista una necesidad operativa real.
9. No obligar al negocio a pasar por el chat cuando una tarea interna puede hacerse mejor con un formulario directo.
10. Si el sistema pide una aclaración breve, debe ser capaz de entender la respuesta breve inmediatamente posterior.
11. Corregir una cita ya creada debe requerir pocos campos y un retorno claro al punto de trabajo.
12. Los filtros de agenda deben ser rápidos, visibles y sin configuración extra.

## Cosas que todavía faltan

Siguientes mejoras razonables:

- filtro rápido por servicio o persona en agenda
- edición simple de categorías de servicio
- uso de capacidad/personal en la disponibilidad real
- acceso rápido a citas pendientes de confirmar
- acciones de cliente desde su ficha, como registrar nota o preparar nueva cita

Todas estas mejoras deben respetar la misma regla: ahorrar tiempo real, no añadir administración innecesaria.
