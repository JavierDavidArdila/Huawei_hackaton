# 🎟️ NEXUS LIVE // T-80
## Motor de Reservas de Alta Concurrencia — Reto Hackathon

<div align="center">

### 🚨 **La venta global abre en 80 minutos.**
### **El motor de reservas dejó de ser confiable.**
### **No hay una versión estable lista para desplegar.**

**Tu misión: reconstruir el núcleo de reservas antes de T-00 usando GLM 5.2 como agente de desarrollo.**

</div>

---

## 📖 Contexto

Son las **08:40 a.m.**

En exactamente **80 minutos**, NEXUS Live abrirá la venta general de entradas para **AURORA WORLD TOUR**, el evento musical más esperado del año.

La campaña ya está activa.

Más de **180.000 personas** están en la sala de espera.

Solo hay **42.000 entradas** disponibles.

El problema es que durante el último despliegue nocturno el componente central de reservas —**SeatLock**— quedó en un estado no confiable.

Los primeros smoke tests muestran comportamientos peligrosos:

- Dos usuarios pueden intentar reservar el mismo asiento al mismo tiempo.
- Algunas reservas vencidas no liberan los asientos.
- Un reintento del cliente puede terminar ejecutando la misma operación dos veces.
- Si el proveedor de pagos tarda demasiado, el sistema puede quedar en un estado ambiguo.
- No existe una forma clara de demostrar por qué un asiento terminó `AVAILABLE`, `HELD` o `SOLD`.

El último artefacto estable no puede utilizarse para esta versión del evento.

El CTO toma una decisión:

> **No vamos a reparar SeatLock. Vamos a reconstruir un motor mínimo, correcto y verificable antes de que abra la venta.**

Ustedes son el equipo asignado.

No recibirán una implementación base.

Recibirán este enunciado, los requisitos del reto y acceso a **GLM 5.2** como agente de desarrollo.

El stack, arquitectura, librerías y estrategia son decisión del equipo.

---

# 📟 NEXUS CONTROL

```text
╔══════════════════════════════════════════════════════════════╗
║                    NEXUS LIVE // WAR ROOM                   ║
╠══════════════════════════════════════════════════════════════╣
║ HORA ACTUAL ...................................... 08:40:00  ║
║ APERTURA DE VENTA ................................ 10:00:00  ║
║ TIEMPO RESTANTE .................................. 01:20:00  ║
╠══════════════════════════════════════════════════════════════╣
║ USUARIOS EN SALA DE ESPERA ......................... 180.000 ║
║ ASIENTOS DISPONIBLES ................................ 42.000 ║
║ MOTOR DE RESERVAS .............................. NO CONFIABLE║
║ PROVEEDOR DE PAGOS ............................... INESTABLE ║
║ CAMPAÑA DE MARKETING ................................. ACTIVA ║
║ ¿SE PUEDE POSPONER LA VENTA? ............................ NO ║
╚══════════════════════════════════════════════════════════════╝
```

---

## ⏱️ Línea de tiempo sugerida — 80 minutos

| Tiempo | Actividad sugerida |
|---|---|
| **0–8 min** | Leer el caso completo, elegir stack y arquitectura, usar GLM 5.2 para construir un plan de implementación. |
| **8–28 min** | Fase 1 — motor de asientos, reservas temporales y estados. |
| **28–46 min** | Fase 2 — idempotencia y concurrencia segura. |
| **46–62 min** | Fase 3 — confirmación, pagos y resiliencia. |
| **62–72 min** | Fase 4 — interfaz visual y simulación. |
| **72–78 min** | Bonos o pruebas adicionales. |
| **78–80 min** | README, bitácora de IA y preparación de entrega. |

> La línea de tiempo es una recomendación. Cada equipo puede distribuir el tiempo como considere conveniente.

---

# 🎯 Objetivo general

Construyan un **sistema de reservas de entradas** capaz de recibir solicitudes de múltiples usuarios y garantizar que un asiento:

```text
AVAILABLE
   ↓
 HELD
   ↓
 SOLD
```

nunca sea vendido a dos compradores diferentes.

El sistema debe permitir:

- Consultar asientos.
- Crear reservas temporales.
- Expirar reservas automáticamente.
- Confirmar compras.
- Procesar reintentos de forma segura.
- Resistir solicitudes concurrentes.
- Integrarse con un proveedor de pagos inestable.
- Explicar las transiciones de estado.
- Ser probado desde una interfaz gráfica sencilla.

La solución puede exponerse mediante **API, backend web, servicio local u otra arquitectura razonable**, siempre que pueda demostrarse y evaluarse claramente.

---

# 🧩 FASE 1 — SeatLock: reservas temporales

Implementen el núcleo del sistema.

Como mínimo, cada asiento debe tener:

- `seat_id`
- `section`
- `price`
- `currency`
- `status`

Los estados mínimos son:

```text
AVAILABLE
HELD
SOLD
```

Una reserva temporal debe contener al menos:

- `hold_id`
- `user_id`
- `event_id`
- lista de `seat_ids`
- `created_at`
- `expires_at`
- `status`

## Operaciones mínimas

La solución debe permitir conceptualmente:

```text
Consultar asientos disponibles
Crear un HOLD
Consultar un HOLD
Liberar un HOLD
```

El nombre exacto de endpoints, funciones o comandos queda a elección del equipo.

## Ejemplo de solicitud de reserva

```json
{
  "user_id": "usr_10482",
  "event_id": "aurora-bogota-2026",
  "seat_ids": [
    "A-101",
    "A-102"
  ]
}
```

## Ejemplo de respuesta exitosa

```json
{
  "hold_id": "hold_8B72A",
  "user_id": "usr_10482",
  "event_id": "aurora-bogota-2026",
  "seat_ids": [
    "A-101",
    "A-102"
  ],
  "status": "HELD",
  "total": 420000,
  "currency": "COP",
  "expires_at": "2026-09-16T14:42:00Z"
}
```

## Reglas obligatorias

### 1. Reserva todo o nada

Si un usuario solicita `A-101`, `A-102` y `A-103`, y `A-102` ya no está disponible, **NO** se debe reservar parcialmente `A-101` y `A-103`.

La operación debe fallar completa.

### 2. Expiración automática

Un HOLD debe expirar automáticamente después de un tiempo configurable.

Valor sugerido:

```text
120 segundos
```

Cuando expire:

```text
HELD → AVAILABLE
```

si el asiento todavía no fue vendido.

### 3. Límite de asientos

Un usuario no puede mantener más de:

```text
6 asientos
```

simultáneamente en reservas activas.

El valor debe poder configurarse.

### 4. El precio lo controla el servidor

El cliente **no debe decidir el precio final**.

El total debe calcularse usando el catálogo de asientos disponible en el servidor.

### 5. Estados válidos

No permitan modificar arbitrariamente `AVAILABLE`, `HELD` o `SOLD` desde una solicitud del cliente.

Las transiciones deben producirse a través de operaciones válidas del dominio.

## Comportamiento esperado

Supongan:

```text
A-101 → AVAILABLE
A-102 → AVAILABLE
```

El usuario `usr_10482` reserva ambos.

Resultado:

```text
A-101 → HELD
A-102 → HELD
```

Un segundo usuario intenta reservar `A-101`.

Resultado esperado:

```text
REJECTED
reason = seat_not_available
```

Si pasan 120 segundos sin completar la compra:

```text
A-101 → AVAILABLE
A-102 → AVAILABLE
```

---

# ⚔️ FASE 2 — La carrera por el último asiento

A las **09:17**, NEXUS ejecuta una simulación de tráfico.

Un solo asiento premium recibe decenas de solicitudes prácticamente al mismo tiempo.

```text
Asiento: VIP-A-001
Solicitudes concurrentes: 100
Disponibilidad: 1
```

El sistema debe garantizar:

```text
EXACTAMENTE UN GANADOR
```

No dos. No tres. No "casi siempre uno".

## Requisito 1 — Concurrencia segura

La estructura usada para cambiar el estado de un asiento debe ser segura frente a solicitudes simultáneas.

El mecanismo concreto queda a elección del equipo.

Pueden considerar, dependiendo de su arquitectura:

- transacciones;
- locks;
- mutex;
- semáforos;
- restricciones únicas;
- compare-and-swap;
- optimistic locking;
- mecanismos atómicos equivalentes.

La elección debe poder explicarse.

## Requisito 2 — Idempotencia

Los clientes móviles pueden reintentar automáticamente una operación si no reciben respuesta.

Por lo tanto, una solicitud puede llegar varias veces aunque el usuario solo haya presionado una vez.

Implementen un mecanismo de idempotencia, por ejemplo mediante:

```text
Idempotency-Key
```

o una estrategia equivalente claramente documentada.

## Comportamiento esperado

Primera solicitud:

```http
Idempotency-Key: reserve-usr10482-001
```

Payload:

```json
{
  "user_id": "usr_10482",
  "event_id": "aurora-bogota-2026",
  "seat_ids": ["VIP-A-001"]
}
```

Respuesta:

```text
HOLD CREADO
hold_id = hold_X1
```

El cliente repite exactamente la misma solicitud con la misma clave.

Resultado esperado:

```text
MISMO RESULTADO LÓGICO
hold_id = hold_X1
```

No debe crearse otro HOLD.

## Conflicto de idempotencia

Si se reutiliza `reserve-usr10482-001`, pero el payload ahora intenta reservar `VIP-A-002`, el sistema debe rechazar la operación como conflicto.

Ejemplo conceptual:

```text
IDEMPOTENCY_CONFLICT
```

## Prueba clave

Simulen múltiples solicitudes concurrentes por el mismo asiento.

```text
100 usuarios
↓
VIP-A-001
↓
1 asiento
```

El resultado final debe demostrar:

```text
1 HOLD exitoso
99 solicitudes rechazadas
0 overselling
```

---

# 💳 FASE 3 — Confirmación y proveedor de pagos inestable

A las **09:32**, el proveedor externo de pagos empieza a mostrar latencia y errores intermitentes.

El sistema ahora debe permitir convertir un HOLD válido en una venta confirmada.

Flujo conceptual:

```text
HOLD válido
    ↓
Validar que no esté expirado
    ↓
Intentar autorización de pago
    ↓
Si APPROVED
    ↓
HELD → SOLD
    ↓
Crear confirmación
```

## Operación de confirmación

Ejemplo conceptual:

```json
{
  "hold_id": "hold_8B72A",
  "payment_token": "tok_test_91827"
}
```

La forma exacta de la API queda a elección del equipo.

## Servicio externo de pagos

Simulen un servicio `mock_payment_authorize()` o un endpoint mock equivalente.

Debe poder producir:

```text
APPROVED
DECLINED
ERROR
TIMEOUT
```

Como referencia:

```text
70% → respuesta normal
10% → declined
10% → error
10% → timeout / demora superior a 2s
```

Los porcentajes no son obligatorios. Lo importante es poder demostrar los escenarios.

## Reglas de consistencia

### Pago aprobado

```text
HELD → SOLD
```

y la compra queda confirmada.

### Pago rechazado

La compra no puede quedar confirmada. El equipo debe definir y documentar qué sucede con el HOLD.

Una solución razonable sería liberar los asientos inmediatamente.

### Timeout o error ambiguo

Un timeout **NO significa automáticamente que el pago fue rechazado**.

El sistema no debe:

- vender el asiento sin certeza;
- duplicar el cobro al reintentar;
- liberar un asiento sin una estrategia coherente mientras exista una operación potencialmente pendiente.

Diseñen una estrategia consistente y explíquenla.

---

# 🔌 Circuit Breaker

Implementen un circuit breaker básico para el proveedor de pagos.

Parámetros sugeridos:

```text
3 fallos consecutivos
↓
OPEN
↓
15 segundos sin llamadas
↓
HALF_OPEN
↓
1 llamada de prueba
```

Estados conceptuales:

```text
CLOSED
OPEN
HALF_OPEN
```

### CLOSED

Las llamadas pasan normalmente.

### OPEN

No se sigue golpeando un servicio degradado.

Una nueva confirmación debería recibir una respuesta segura, por ejemplo:

```text
PAYMENT_SERVICE_UNAVAILABLE
```

El asiento **NO** debe marcarse como `SOLD`.

### HALF_OPEN

Después del tiempo configurado, se permite una llamada de prueba.

Si funciona:

```text
HALF_OPEN → CLOSED
```

Si falla:

```text
HALF_OPEN → OPEN
```

---

# 🧾 Trazabilidad mínima

Cada cambio importante debe poder explicarse.

Para una reserva o compra debe ser posible identificar al menos:

- `user_id`
- `hold_id`
- asientos afectados
- estado anterior
- estado nuevo
- timestamp
- motivo de la transición

Ejemplo:

```json
{
  "hold_id": "hold_8B72A",
  "seat_id": "A-101",
  "from": "HELD",
  "to": "SOLD",
  "reason": "payment_approved",
  "timestamp": "2026-09-16T14:51:07Z"
}
```

No es obligatorio utilizar una base de datos externa.

La solución puede usar memoria, archivos, SQLite, PostgreSQL u otra estrategia.

La decisión forma parte del diseño del equipo.

---

# 🖥️ FASE 4 — NEXUS Control Room

Los jueces deben poder probar el sistema **sin escribir JSON, usar curl ni abrir Postman**.

Construyan una interfaz gráfica sencilla.

No se evalúa diseño visual avanzado. Se evalúa claridad y funcionalidad.

## La interfaz debe permitir como mínimo

### 1. Visualizar asientos

Mostrar algunos asientos con estados distinguibles:

```text
🟢 AVAILABLE
🟡 HELD
🔴 SOLD
```

### 2. Seleccionar asientos

El juez debe poder seleccionar uno o varios asientos y crear un HOLD.

### 3. Mostrar información de la reserva

Por ejemplo:

```text
Hold ID
Usuario
Asientos
Total
Tiempo restante
Estado
```

### 4. Confirmar compra

Debe poder ingresar o generar un `payment_token` de prueba y ejecutar la confirmación.

### 5. Simular una carrera

Incluyan una forma sencilla de demostrar concurrencia, por ejemplo:

```text
SIMULAR 20 USUARIOS POR ESTE ASIENTO
```

La interfaz debe mostrar claramente:

```text
20 solicitudes
1 ganador
19 rechazadas
```

---

# 🧪 Escenarios que el jurado debería poder verificar

## Escenario A — Reserva normal

```text
Asiento disponible
↓
Crear HOLD
↓
Estado = HELD
↓
Pago aprobado
↓
Estado = SOLD
```

## Escenario B — Reserva expirada

```text
Crear HOLD
↓
No pagar
↓
Esperar TTL
↓
Asiento vuelve a AVAILABLE
```

Para la demo pueden permitir configurar un TTL más corto.

## Escenario C — Concurrencia

```text
20+ solicitudes
↓
Mismo asiento
↓
Solo 1 HOLD
```

## Escenario D — Reintento

```text
Misma Idempotency-Key
+
Mismo payload
↓
Mismo resultado lógico
```

## Escenario E — Conflicto

```text
Misma Idempotency-Key
+
Payload diferente
↓
IDEMPOTENCY_CONFLICT
```

## Escenario F — Pago degradado

```text
Proveedor falla repetidamente
↓
Circuit breaker OPEN
↓
Sistema continúa respondiendo
↓
Asiento NO termina SOLD incorrectamente
```

---

# 🤖 Uso obligatorio de GLM 5.2

GLM 5.2 será el agente de desarrollo principal durante el reto.

Se espera que los equipos lo utilicen para actividades como:

- analizar el enunciado;
- definir arquitectura;
- diseñar modelos;
- generar código;
- crear pruebas;
- identificar race conditions;
- revisar seguridad;
- analizar logs;
- investigar errores;
- refactorizar;
- crear la interfaz;
- revisar decisiones de diseño.

No se evalúa cuántos prompts enviaron.

Se evalúa **qué tan efectivamente utilizaron el agente**.

---

# 📝 Bitácora de IA

Incluyan un archivo, por ejemplo:

```text
docs/sesion_ia.md
```

o:

```text
prompts.md
```

No es necesario copiar toda la conversación.

Incluyan, por ejemplo:

- Prompt inicial de arquitectura.
- Prompt que permitió resolver un problema importante.
- Una propuesta de GLM 5.2 que tuvieron que corregir.
- Un error encontrado con ayuda del agente.
- Una decisión en la que el equipo no siguió la primera recomendación del modelo.

---

# 💎 BONOS

Los bonos son opcionales.

> **Un bono bien implementado vale más que varios bonos superficiales.**

## 🥇 Bono A — Sala de espera justa
### Hasta +8 puntos

Construyan una pequeña estrategia de cola o waitlist para evitar que miles de usuarios golpeen simultáneamente el motor de reservas.

La solución debe poder explicar:

- orden de atención;
- criterio de fairness;
- cómo evita que un usuario monopolice múltiples reservas;
- qué ocurre si un usuario abandona.

No es necesario construir una infraestructura distribuida real.

## 🥈 Bono B — Prueba de concurrencia real
### Hasta +8 puntos

Construyan una prueba automatizada de carga o concurrencia que demuestre:

```text
N solicitudes simultáneas
+
1 asiento
=
1 ganador
```

Herramientas posibles:

- pytest concurrente;
- k6;
- Locust;
- Artillery;
- threads;
- procesos;
- async tasks;
- otra herramienta razonable.

## 🥉 Bono C — Registro de auditoría reproducible
### Hasta +7 puntos

Construyan un historial suficientemente estructurado para reconstruir la vida de una reserva:

```text
AVAILABLE
↓
HELD
↓
PAYMENT_ATTEMPT
↓
PAYMENT_APPROVED
↓
SOLD
```

Debe ser posible consultar o exportar esa trazabilidad.

## 🧠 Bono D — GLM 5.2 dentro del producto
### Hasta +7 puntos

Además de utilizar GLM 5.2 para desarrollar, intégrenlo de manera útil dentro de la solución.

Ejemplo: un módulo de operaciones recibe historial de una reserva, eventos de pago, cambios de estado y errores, y genera una explicación operacional estructurada.

Debe manejar al menos:

- timeout;
- respuesta vacía;
- error de API;
- formato inesperado.

No se otorgan puntos únicamente por hacer una llamada al modelo.

---

# 📦 Entregables

La entrega debe incluir como mínimo:

1. **Código fuente funcional.**
2. **README.md**.
3. **Archivo de dependencias** apropiado al stack.
4. **Bitácora de uso de GLM 5.2**.
5. **Instrucciones claras para ejecutar la aplicación.**
6. **Tests creados por el equipo.**
7. **Interfaz gráfica funcional.**

---

# 📘 El README del equipo debe indicar

- Stack seleccionado.
- Arquitectura.
- Cómo instalar dependencias.
- Cómo iniciar el sistema.
- Cómo ejecutar pruebas.
- Cómo abrir la interfaz.
- Cómo simular concurrencia.
- Estrategia de idempotencia.
- Estrategia para evitar overselling.
- Manejo de expiración de HOLDs.
- Estrategia ante fallos del proveedor de pagos.
- Bonos implementados.

---

# 🧾 Rúbrica de evaluación

Cada criterio puede calificarse como:

```text
0%   → No implementado / no funciona
50%  → Parcial / funciona con limitaciones importantes
100% → Implementado correctamente y demostrable
```

| Categoría | Criterio | Máx. |
|---|---|---:|
| **Motor de reservas** | Estados `AVAILABLE / HELD / SOLD`, reserva todo-o-nada, TTL y límites configurables | 12 |
| | Cálculo correcto del precio y validaciones de dominio | 6 |
| **Concurrencia e idempotencia** | Evita double booking bajo solicitudes concurrentes | 12 |
| | Idempotencia correcta: replay y conflicto | 8 |
| **Checkout y resiliencia** | Confirmación coherente ante APPROVED / DECLINED / ERROR / TIMEOUT | 10 |
| | Circuit breaker funcional y degradación segura | 8 |
| **Trazabilidad** | Cambios de estado explicables y verificables | 6 |
| **Interfaz gráfica** | Permite reservar, confirmar y visualizar estados sin herramientas externas | 8 |
| | Permite demostrar una carrera de múltiples compradores | 4 |
| **Calidad técnica** | Arquitectura, modularidad, manejo de errores y claridad del código | 8 |
| **Uso efectivo de GLM 5.2** | Bitácora demuestra uso iterativo, debugging y pensamiento crítico | 10 |
| **Demo** | El equipo demuestra los escenarios principales de forma clara | 8 |
| **Subtotal base** |  | **100** |
| **Bonos** | A + B + C + D | **hasta +30** |

---

# ⚠️ Casos límite que deberían considerar

No se entregará una lista completa de pruebas.

Sin embargo, un sistema robusto debería pensar en situaciones como:

- `seat_ids` vacío;
- asiento inexistente;
- asiento duplicado en la misma solicitud;
- usuario inexistente o vacío;
- HOLD ya expirado;
- confirmar dos veces el mismo HOLD;
- confirmar un HOLD ya vendido;
- payment token vacío;
- solicitud simultánea durante expiración;
- reintento después de timeout;
- cantidad de asientos superior al límite;
- mismo asiento solicitado por múltiples usuarios;
- mismo usuario con varios HOLD activos;
- proveedor de pagos lento;
- proveedor de pagos completamente caído.

No necesariamente deben resolver cada escenario de la misma manera.

Sí deben evitar estados imposibles o comportamientos silenciosamente incorrectos.

---

# 🛠️ Libertad tecnológica

El equipo decide cómo resolver el problema.

Pueden utilizar Python, Java, JavaScript/TypeScript, Go, C#, bases de datos, memoria, SQLite, PostgreSQL, Redis, Docker, frameworks web, herramientas de testing o cualquier combinación razonable.

La elección del stack **no otorga puntos por sí sola**.

La solución debe ser:

```text
EJECUTABLE
COMPRENSIBLE
DEMOSTRABLE
ROBUSTA
```

---

# 🚫 Restricciones

No se permite:

- hardcodear respuestas exclusivamente para pasar los ejemplos;
- devolver resultados estáticos;
- falsear resultados de concurrencia;
- incluir credenciales en el repositorio;
- afirmar que algo es thread-safe sin poder demostrarlo;
- utilizar GLM 5.2 únicamente para generar documentación y afirmar que fue usado como agente de desarrollo.

---

# 🏁 MENSAJE FINAL

```text
╔══════════════════════════════════════════════════════════════╗
║                     NEXUS LIVE // T-80                      ║
╠══════════════════════════════════════════════════════════════╣
║ VENTA GLOBAL ..................................... T-80:00   ║
║ USUARIOS EN ESPERA ................................. 180.000 ║
║ ASIENTOS ............................................ 42.000 ║
║ MOTOR DE RESERVAS .............................. NO CONFIABLE║
║ GLM 5.2 .......................................... DISPONIBLE║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║              SU EQUIPO ES EL NUEVO SEATLOCK.                 ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

**Construyan rápido.**

**Prueben más rápido.**

**Y recuerden: si dos personas compran el mismo asiento, alguien tendrá que explicarlo.**
