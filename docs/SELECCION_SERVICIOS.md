# Selección de servicios

Esta demo no usa un LLM externo para elegir servicios. Usa una lógica local y prudente sobre los servicios reales configurados en `demo/data/negocio.json`.

## Qué problema corrige

Antes, un alias genérico como `corte de pelo` podía estar asociado a una variante concreta y provocar respuestas incorrectas.

Ejemplo de fallo corregido:

```text
Usuario: Hola. Quisiera un corte de pelo. Soy hombre
Antes: Corte mujer
Ahora: Corte caballero
```

## Estrategia actual

El matcher analiza el mensaje y compara contra cada servicio configurado.

Tiene en cuenta:

- nombre real del servicio
- `id` del servicio
- alias configurados
- intención principal: corte, peinado, color, mechas, decoloración, uñas, manicura, pedicura, barba
- modificadores: hombre/caballero, mujer/señora, niño/niña/infantil/hijo/hija
- coincidencias exactas o parciales
- conflictos entre modificadores incompatibles

Después calcula una puntuación por servicio.

Un servicio con modificador correcto gana frente a una coincidencia genérica. Un servicio con modificador incompatible se penaliza fuerte.

## Cuándo responde con un servicio

Responde con un servicio concreto cuando hay una coincidencia clara.

Ejemplos:

```text
Quiero un corte de pelo. Soy hombre
=> Corte caballero

Necesito mechas
=> Mechas

Quiero afeitarme la barba
=> Arreglo de barba

Quiero un corte para mi hijo
=> Corte infantil
```

## Cuándo pide aclaración

Pide aclaración si el mensaje es demasiado genérico y existen varias opciones reales configuradas.

Ejemplos:

```text
Quiero un corte
=> ¿Te refieres a Corte caballero, Corte mujer o Corte infantil?

Quiero uñas
=> ¿Te refieres a Manicura o Uñas gel?
```

También pide aclaración si el usuario mezcla servicios y la demo no gestiona todavía reservas combinadas.

```text
Quiero color y peinado
=> Ahora mismo registro una solicitud por servicio. ¿Quieres que lo dejemos como Coloración o Peinado?
```

## Configuración

Los servicios siguen viviendo en `demo/data/negocio.json`.

Para mejorar o adaptar otro negocio, edita:

- `name`
- `category`
- `aliases`
- `price`
- `duration`
- `duration_minutes`
- `rules`, si aplica

No conviene poner alias genéricos en una variante concreta.

Mal ejemplo:

```json
"Corte mujer": ["corte", "corte de pelo"]
```

Mejor:

```json
"Corte mujer": ["corte mujer", "corte de mujer", "corte femenino"]
"Corte caballero": ["corte hombre", "corte de caballero", "corte masculino"]
"Corte infantil": ["corte niño", "corte niña", "corte infantil"]
```

La lógica general puede tener listas de sinónimos, pero no inventa servicios fuera de la configuración.

## Memoria corta de aclaración

Cuando el bot acaba de pedir una aclaración de servicio, guarda esa aclaración durante pocos turnos.

Eso permite respuestas cortas como:

```text
quiero un corte
hombre
```

o:

```text
quiero uñas
gel
```

La respuesta breve se resuelve solo contra las opciones candidatas que el bot acababa de ofrecer. Si no encaja, la conversación vuelve al flujo general.

## Limitaciones

- Solo gestiona una solicitud por servicio.
- No crea combinaciones automáticas de servicios.
- No entiende todas las variantes coloquiales posibles.
- Si el servicio no está configurado, no debe venderlo como disponible.
- La disponibilidad avanzada por duración, personal y capacidad sigue siendo una fase posterior.
