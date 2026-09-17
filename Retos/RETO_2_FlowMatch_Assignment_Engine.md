# 🧩 FlowMatch Assignment Engine — Reto Hackathon

## 📖 El contexto

Son las **12:58 p.m. del viernes**. En 2 minutos arranca la hora pico del almuerzo en **QuickBite**, una app de domicilios que conecta pedidos con repartidores en la ciudad.

El problema de siempre se multiplica en la hora pico: **llegan muchos más pedidos que repartidores disponibles**. Alguien tiene que decidir, en tiempo real, **a qué repartidor asignar cada pedido** — tomando en cuenta qué tan lejos está, qué tan urgente es el pedido y cuánto cuesta ese envío — sin dejar a ningún repartidor sobrecargado y sin que los pedidos importantes se queden esperando.

Hoy lo hacen "a mano" con reglas fijas en una hoja de cálculo: es lento, no reacciona cuando entran ráfagas de pedidos, y el viernes pasado la app **colapsó** — asignó 8 pedidos al mismo repartidor y dejó a 30 clientes esperando más de una hora.

El líder de operaciones les asigna la tarea: construir, durante esta hora pico, un **motor de asignación en tiempo real** capaz de:

- Decidir, para cada pedido que entra, **a qué repartidor asignarlo** (o si toca ponerlo en espera).
- Respetar **límites y prioridades** (un repartidor no puede tener demasiados pedidos a la vez, los pedidos urgentes van primero).
- Explicar **por qué** tomó esa decisión — porque el equipo de soporte necesita saber por qué un pedido quedó en espera cuando un cliente reclama.

Van a construir **FlowMatch Assignment Engine** usando un modelo de IA (**GLM 5.2**) como copiloto de desarrollo. Tienen el caso completo abajo, organizado en fases que se construyen una sobre otra: **no salten fases**, porque cada una es prerrequisito de la siguiente (igual que en producción, donde no puedes optimizar el costo de los envíos sin antes tener funcionando la asignación básica que respeta los límites de cada repartidor).

---

## ⏱ Línea de tiempo sugerida (80 minutos)

| Tiempo | Actividad |
| --- | --- |
| **0–8 min** | Leer el caso completo, definir arquitectura y stack con el equipo, primer prompt de planeación a la IA. |
| **8–30 min** | Fase 1 y Fase 2 (asignación base + prioridades + control de ráfagas). |
| **30–50 min** | Fase 3 (optimización de costo + resiliencia ante servicio externo). |
| **50–62 min** | Fase 4 (interfaz gráfica de verificación). |
| **62–74 min** | Bonos (elegir 1 o 2, no todos) + pruebas de borde. |
| **74–80 min** | Cerrar bitácora de prompts, README y dependencias; repaso final de entregables. |

---

## 🎯 Objetivo general

Construir un servicio (**API o CLI**, a elección del equipo) que reciba un **pedido** (más el estado actual de los repartidores) y devuelva una **decisión de asignación**, junto con:

- Un **estado del pedido** (`ASSIGNED` / `QUEUED` / `REJECTED`).
- El **repartidor asignado** (si aplica).
- Una **explicación** de por qué se tomó esa decisión y qué reglas mandaron.
- El **costo** estimado del envío.

El sistema debe **respetar los límites de cada repartidor** (no asignarle más pedidos de los que puede manejar), soportar **ráfagas de pedidos concurrentes** sin corromper su estado interno (carga de cada repartidor, cola de espera), y exponer una **interfaz gráfica sencilla** (Fase 4) para que cualquier persona — incluyendo los jueces — pueda enviar un pedido a mano y ver la decisión sin tocar código ni usar Postman.

### 📤 Formato de salida (crece con cada fase)

Todas las fases devuelven **el mismo objeto**, que se va enriqueciendo. Así se ve la progresión:

| Campo | Aparece desde | Descripción |
| --- | --- | --- |
| `order_id` | Fase 1 | Identificador del pedido evaluado. |
| `status` | Fase 1 | `ASSIGNED` / `QUEUED` / `REJECTED`. |
| `assigned_courier` | Fase 1 | ID del repartidor asignado, o `null` si quedó en espera/rechazado. |
| `reasons[]` | Fase 1 | Lista de reglas aplicadas, cada una con `rule` y `detail`. Crece en Fase 2 (control de ráfagas). |
| `cost` | Fase 3 | Costo estimado del envío en COP. |
| `pricing_status` | Fase 3 | Estado del circuit breaker del servicio de tarifas. |

Cada ejemplo de salida en las fases siguientes usa exactamente este formato.

---

## 🧩 Fases de desarrollo

### FASE 1 · Asignación base por prioridad

Reciban un pedido con al menos: `order_id`, `timestamp` (ISO 8601), `pickup_zone` (zona de recogida), `distance_km` (distancia estimada del envío), `priority` (`normal` o `express`), y el **estado de los repartidores disponibles**, donde cada repartidor tiene: `courier_id`, `zone` (zona actual), `active_orders` (pedidos que ya lleva encima), `max_capacity` (máximo que puede manejar a la vez).

**Ejemplo de entrada:**

```json
{
  "order_id": "ord_00234",
  "timestamp": "2024-11-28T12:58:00Z",
  "pickup_zone": "centro",
  "distance_km": 3.2,
  "priority": "express",
  "couriers": [
    { "courier_id": "cour_A", "zone": "centro", "active_orders": 1, "max_capacity": 3 },
    { "courier_id": "cour_B", "zone": "norte",  "active_orders": 0, "max_capacity": 3 },
    { "courier_id": "cour_C", "zone": "centro", "active_orders": 3, "max_capacity": 3 }
  ]
}
```

Implementen un endpoint/función `assign(order)` que elija el mejor repartidor respetando un **orden de prioridad** y al menos **3 reglas base configurables**:

1. **Misma zona primero:** preferir repartidores que ya están en la `pickup_zone` del pedido (menos tiempo de recogida).
2. **Respetar capacidad:** nunca asignar a un repartidor que ya está en su `max_capacity`. Si todos los candidatos están llenos, el pedido va a `QUEUED` (cola de espera).
3. **Menor carga primero:** entre los repartidores válidos, preferir al que tenga **menos `active_orders`** para repartir el trabajo de forma pareja.

- Cada regla/parámetro (orden de preferencia, uso de zona, etc.) debe poder **activarse/desactivarse** y ajustarse (ej. vía archivo de config o parámetros).
- **Persistencia en memoria** está bien (no se requiere base de datos externa). Los `active_orders` de un repartidor **deben actualizarse** cuando se le asigna un pedido.

> **Comportamiento esperado con el ejemplo de arriba:** el pedido es de la zona `centro`. Candidatos en `centro`: `cour_A` (1 pedido) y `cour_C` (lleno, 3/3 → descartado). `cour_A` tiene capacidad y menos carga → se le asigna. Estado **`ASSIGNED`** a `cour_A`.

**Salida esperada de la Fase 1** (aún sin control de ráfagas ni costo de fase 3):

```json
{
  "order_id": "ord_00234",
  "status": "ASSIGNED",
  "assigned_courier": "cour_A",
  "reasons": [
    { "rule": "same_zone_preferred", "detail": "cour_A is in pickup_zone=centro" },
    { "rule": "capacity_ok", "detail": "cour_A at 1/3 (cour_C skipped: 3/3 full)" },
    { "rule": "least_loaded", "detail": "cour_A chosen (1 active order, lowest among valid)" }
  ]
}
```

> Si **ningún** repartidor tuviera capacidad, el resultado sería `status: "QUEUED"`, `assigned_courier: null` y una razón `"all_couriers_at_capacity"`.

---

### FASE 2 · Control de ráfagas (ventanas deslizantes)

En la hora pico entran ráfagas de pedidos en segundos. Hay que evitar saturar a un repartidor o a una zona. Implementen, sobre una **secuencia de pedidos** (usando el historial reciente):

- **Límite de ritmo por repartidor (ventana deslizante):** un mismo repartidor no puede recibir más de **N pedidos nuevos en una ventana de tiempo** (ej. máx. 3 pedidos en 10 segundos, configurable), aunque tenga capacidad libre — se le da tiempo de arrancar. Usar **ventana deslizante (sliding window)**, no ventana fija ingenua.
- **Balanceo de zona:** si una misma `pickup_zone` recibe una avalancha de pedidos, repartir entre repartidores de zonas vecinas antes que sobrecargar la zona.
- **Modo de contención por saturación sostenida:** si durante una **ventana deslizante** (ej. 3 pedidos consecutivos) **todos** los repartidores están al tope y la cola de espera sigue creciendo, entrar en **modo de contención temporal**: los nuevos pedidos `normal` se **rechazan de inmediato** (`REJECTED`) por, por ejemplo, **120 segundos**, con **expiración automática** — para proteger el servicio de los pedidos ya aceptados. Los pedidos `express` siguen intentando encolarse.

**Ejemplo de comportamiento esperado:** llegan 6 pedidos a la zona `centro` en 7 segundos mientras todos los repartidores se van llenando. El pedido **#6** debe:

- Detectar que se superó el ritmo/saturación (todos al tope, cola creciendo por 3 pedidos seguidos).
- Activar el **modo de contención temporal**.
- Devolver, para un pedido `normal`, estado `REJECTED` con razón `"surge_protection_active: all couriers full, queue growing for 3 orders"`.
- Mientras dure la contención (siguientes 120s), nuevos pedidos `normal` se rechazan **inmediatamente**, con razón `"surge_window_active"`, sin volver a recorrer toda la lista de repartidores.

**Salida esperada del pedido #6** (pedido `normal`, todos los repartidores llenos, contención activada):

```json
{
  "order_id": "ord_00239",
  "status": "REJECTED",
  "assigned_courier": null,
  "reasons": [
    { "rule": "capacity_ok", "detail": "0 couriers with free capacity" },
    { "rule": "surge_protection_active", "detail": "all couriers full, queue growing for 3 orders (window=120s)" }
  ]
}
```

> Un pedido **#7** `normal` que llegue dentro de los 120s trae directamente la razón `"surge_window_active"` sin recalcular. Un pedido `express` en cambio intenta encolarse (`QUEUED`) en vez de rechazarse.

---

### FASE 3 · Optimización de costo + resiliencia

- Combinando todas las reglas (fase 1 y 2), cuando haya **varios repartidores válidos** la decisión debe **minimizar el costo del envío** (por ejemplo, menor `distance_km` recorrida) y clasificar el estado con umbrales claros:
  - `ASSIGNED`: se encontró un repartidor válido y se le asignó.
  - `QUEUED`: no hay repartidor disponible ahora, pero el pedido entra en cola de espera para reintentar.
  - `REJECTED`: contención por saturación activa (o pedido inválido).
- Simulen una llamada a un servicio externo de **cálculo de tarifa dinámica** (`mock_pricing()`) que aleatoriamente falla o demora (timeout) — por ejemplo, **30% de probabilidad** de fallar o tardar >2s.
- Implementen un **circuit breaker**:
  - Si el servicio falla **3 veces seguidas**, el circuito se **"abre"** y deja de llamarlo por, por ejemplo, **15 segundos**, degradando de forma segura (ej: usar una **tarifa base fija** y marcar el pedido como precio degradado, en vez de fallar toda la asignación).
  - Pasado ese tiempo, el circuito pasa a **"semi-abierto"** e intenta de nuevo con una sola llamada de prueba.
- Cada respuesta debe incluir el **desglose** de la decisión: qué repartidor se eligió (o por qué no), qué reglas se activaron y el costo resultante.

**Salida esperada de la Fase 3** — es la misma estructura de las fases anteriores, ahora **enriquecida con dos campos nuevos**: `cost` (COP del envío) y `pricing_status` (estado del circuit breaker). Para el pedido de ejemplo de la Fase 1:

```json
{
  "order_id": "ord_00234",
  "status": "ASSIGNED",
  "assigned_courier": "cour_A",
  "cost": 6800,
  "reasons": [
    { "rule": "same_zone_preferred", "detail": "cour_A is in pickup_zone=centro" },
    { "rule": "capacity_ok", "detail": "cour_A at 1/3 (cour_C skipped: 3/3 full)" },
    { "rule": "least_loaded", "detail": "cour_A chosen (1 active order, lowest among valid)" }
  ],
  "pricing_status": "circuit_open_degraded_flat_rate"
}
```

---

### FASE 4 · Interfaz gráfica de verificación

Toda la lógica de las fases anteriores debe poder probarse **sin usar consola, curl ni Postman**. Construyan una interfaz gráfica sencilla (página web local, app de escritorio simple, o incluso un notebook con widgets interactivos — lo que el equipo prefiera) que permita:

- **Ingresar un pedido** mediante un formulario con campos para cada atributo (`pickup_zone`, `distance_km`, `priority`) — no es necesario escribir JSON a mano. El estado de los repartidores puede venir precargado o editarse en la misma interfaz.
- **Mostrar la decisión** de forma clara al enviar: el estado (`ASSIGNED`/`QUEUED`/`REJECTED` — idealmente con color: verde/amarillo/rojo), el repartidor asignado, el costo y el desglose de reglas aplicadas.
- **Permitir simular una ráfaga:** un botón o campo que dispare N pedidos seguidos a la misma zona (por ejemplo, reenviando el formulario 6 veces rápido), para que el jurado vea en vivo cómo los primeros pedidos se asignan, cómo se van llenando los repartidores y cómo el sistema entra en contención por saturación (`REJECTED`) sin necesidad de mirar logs de consola.


**Ejemplo de flujo esperado:** el juez abre la interfaz en el navegador, llena el formulario con los datos del ejemplo de la Fase 1, presiona **"Asignar"** y ve en pantalla: `ASSIGNED → cour_A · Costo: $6.800` junto con las razones. Luego presiona **"Simular ráfaga (6x)"** en la misma zona y ve cómo los primeros pedidos se asignan/encolan normalmente y el 6º sale en rojo como `REJECTED` — `surge_protection_active`.

---

## 💎 Requerimientos bono (puntos extra)

> Elijan estratégicamente — **no es necesario implementar todos**. Bien resuelto, un solo bono avanzado vale más que varios superficiales.

### Bono A — Optimización global por lotes (hasta +10 pts)
En vez de asignar pedido a pedido de forma miope (greedy), agrupen los pedidos que llegan en una **ventana corta** y resuelvan la **mejor asignación conjunta** pedido↔repartidor que minimice el costo total (una asignación tipo "emparejamiento óptimo"). Expliquen por qué la asignación por lotes supera a la codiciosa (ej. un caso donde el greedy deja un pedido lejano varado y el lote lo resuelve mejor).

### Bono B — Concurrencia segura (hasta +8 pts)
Demuestren (con una **prueba de carga/concurrencia real**, no solo afirmándolo) que el **estado compartido de la carga de cada repartidor (`active_orders`) y la cola de espera** es seguro ante N hilos/requests simultáneos asignando al mismo tiempo, sin condiciones de carrera que asignen dos pedidos al mismo cupo (sobre-asignación) o que dejen el conteo descuadrado.

### Bono C — Explicabilidad exportable (hasta +6 pts)
Generen, para cada pedido en `REJECTED`, un **reporte estructurado (JSON)** apto para el equipo de soporte: reglas activadas, estado de los repartidores en ese momento, timestamp, y una **explicación en lenguaje natural** generada por la IA a partir de esos datos (para responderle al cliente por qué su pedido no se pudo tomar).

### Bono D — Suite de pruebas de escenarios extremos (hasta +6 pts)
Escriban un set de **pruebas automatizadas** que simule escenarios críticos (ráfaga de pedidos a una sola zona, todos los repartidores llenos de golpe, avalancha de pedidos `express`, entrada de pedidos justo cuando expira la ventana de contención) y verifiquen que el sistema reacciona correctamente y **nunca sobre-asigna** a un repartidor por encima de su capacidad.

---

## 📦 Entregables

1. **Código fuente funcional** (repositorio o carpeta comprimida).
2. **README** con: arquitectura elegida, decisiones de diseño, cómo correr el proyecto, y qué bonos implementaron.
3. **Bitácora de prompts:** registro de los prompts clave usados con GLM 5.2 y cómo iteraron sobre las respuestas (esto es evaluado — no basta con "generé todo con un prompt").
4. **Archivo de dependencias** (`requirements.txt` o equivalente según el stack) que liste todas las dependencias necesarias para correr el proyecto.

---

## 🧾 Rúbrica de evaluación

> Diseñada para calificar rápido: cada ítem se puntúa **0** (no cumple) / **1** (cumple parcial) / **2** (cumple bien). Multiplicar por el peso indicado.

| Categoría | Criterio | Puntaje máx. |
| --- | --- | --- |
| **Funcionalidad core** (38 pts) | Fase 1: asignación base + prioridad + respeto de capacidad, funcionando y configurable (ver ejemplo Fase 1) | 10 |
| | Fase 2: control de ráfagas por ventana deslizante + contención con auto-expiración funcionando como en el ejemplo | 10 |
| | Fase 3: optimización de costo + circuit breaker con degradación segura | 10 |
| | Clasificación de estado (ASSIGNED/QUEUED/REJECTED) correctamente aplicada en casos de prueba | 8 |
| **Calidad técnica** (20 pts) | Arquitectura clara, modular, separación de responsabilidades | 11 |
| | Manejo de errores y casos borde (pedido sin repartidores, distancia negativa, prioridad inválida, timestamps futuros, etc.) | 9 |
| **Explicabilidad** (14 pts) | Cada decisión trae razones claras y trazables a reglas específicas, con formato tipo el ejemplo de salida | 14 |
| **Interfaz gráfica** (13 pts) | Permite ingresar un pedido por formulario (sin curl/Postman) y muestra estado + repartidor + costo + razones | 8 |
| | Permite simular una ráfaga y visualizar en vivo la contención por saturación | 5 |
| **Uso efectivo de IA** (15 pts) | Bitácora de prompts muestra iteración y pensamiento crítico, no copy-paste ciego | 10 |
| | Evidencia de que el equipo entendió y pudo explicar el código generado | 5 |
| **Subtotal base** | | **100** |
| **Bonos** | Bono A (lotes) + Bono B (concurrencia) + Bono C (soporte) + Bono D (escenarios extremos) | hasta **+30** |

> **Nota de calificación:** cada criterio se puntúa como fracción de su máximo (0%, 50% o 100% de cumplimiento) para mantener la evaluación objetiva y rápida — no hay que inventar escalas distintas por fila.

**Puntaje final** = subtotal base (máx. 100) + bonos (máx. 30) → escala final sobre **130**, normalizable a 100 si se requiere comparar contra otras hackathons del evento.
