# Canales y WhatsApp

## Qué es un canal

Un canal es una entrada o salida configurable del negocio.

Ejemplos:

- webchat
- WhatsApp
- email
- Telegram

El sistema no debe asumir que un negocio usa siempre el mismo canal. Tampoco debe tener números o credenciales hardcodeadas en el código.

## Por qué WhatsApp es configuración

WhatsApp pertenece a la configuración del negocio porque cambia entre clientes:

- número del negocio
- nombre visible
- estado activo/inactivo
- modo de integración
- referencias técnicas futuras

Por eso se guarda en SQLite en una tabla de canales y se edita desde panel.

## Qué se puede hacer ya

Rutas:

```text
/config/canales
/config/canales/whatsapp
```

Desde el panel se puede:

- ver si WhatsApp está configurado
- crear la configuración
- editar número
- editar nombre visible
- cambiar modo
- activar o desactivar el canal
- guardar una referencia técnica opcional

Si el canal está activo y tiene número, la app genera un enlace de contacto tipo:

```text
https://wa.me/<numero>
```

Ese enlace puede usarse para botones, contacto directo o QR.

Además, la capa conversacional ya puede aprovechar el número entrante del canal WhatsApp aunque la integración real todavía no exista.

En esta fase:

- si el mensaje entra con `channel=whatsapp` e `incoming_phone`
- el sistema normaliza ese teléfono
- busca la clienta en la base
- si la encuentra, reutiliza la ficha y evita pedir teléfono otra vez
- si no la encuentra, usa ese número como contacto para el flujo de cliente nuevo

## Modos del canal

```text
demo
preparado
conectado
```

- `demo`: configuración local útil para enseñar el flujo.
- `preparado`: datos listos para una integración futura, pero sin conexión real.
- `conectado`: reservado para cuando exista integración real con API/webhooks.

En esta fase, incluso si se selecciona `conectado`, el sistema no llama a Meta. Conviene usar ese modo solo cuando haya integración real implementada.

## Estructura de datos

Tabla:

```text
canales
```

Campos:

- `id`
- `tipo_canal`
- `activo`
- `modo`
- `telefono`
- `nombre_visible`
- `config_json`
- `created_at`
- `updated_at`

Para WhatsApp:

- `tipo_canal = whatsapp`
- `telefono` debería guardarse en formato internacional, por ejemplo `+34928123456`
- `config_json` queda como campo flexible para referencias futuras

## Qué no se hace todavía

- No se conecta con WhatsApp Business Platform.
- No se usa Meta Cloud API.
- No se reciben mensajes entrantes por webhook.
- No se envían respuestas automáticas por WhatsApp.
- No se validan credenciales.
- No se comprueba el estado real del número en Meta.
- No hay onboarding oficial del canal.

## Comportamiento conversacional actual

Número conocido:

- saludo corto y prudente por nombre
- reutilización de ficha
- sin pedir teléfono otra vez

Número desconocido:

- flujo normal
- el teléfono entrante ya se usa como contacto
- se pide nombre solo si hace falta

Corrección de identidad:

- si la persona dice de forma explícita que no es la clienta esperada o da otro nombre
- el sistema continúa con prudencia
- evita asumir demasiado en las respuestas siguientes
- no bloquea la conversación

## Cómo encajaría una integración real

Una fase futura debería añadir:

- credenciales seguras fuera del repositorio
- `phone_number_id`
- `business_account_id`
- token de acceso gestionado con seguridad
- endpoint de webhook
- validación de webhook
- recepción de mensajes entrantes
- envío de respuestas
- registro de conversaciones por canal
- control de errores y estado del canal

Ubicación conceptual:

- configuración del canal: `canales`
- recepción/envío técnico: módulo futuro de adaptador WhatsApp
- interpretación del mensaje: capa inteligente existente
- creación de citas/clientes: núcleo operativo existente

La regla importante: WhatsApp debe alimentar el sistema, no sustituirlo ni mezclarse con la lógica de negocio.
