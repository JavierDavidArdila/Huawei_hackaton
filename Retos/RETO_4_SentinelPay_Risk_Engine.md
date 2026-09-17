# 🛡️ SentinelPay Risk Engine — Reto Hackathon

## 📖 El contexto

Son las **11:58 p.m. del 27 de noviembre**. En 2 minutos arranca el Black Friday más grande en la historia de **SentinelPay**, una pasarela de pagos que procesa transacciones para más de **4.000 comercios** en Latinoamérica.

El equipo de fraude acaba de detectar algo inusual en las pruebas de carga: una red de tarjetas robadas está siendo probada en microtransacciones (**"card testing"**) contra varios comercios pequeños, usando dispositivos e IPs compartidos para evadir los filtros actuales.

El sistema de reglas estático que tienen hoy no da abasto: es lento, no aprende de patrones, y ya dejó pasar operaciones fraudulentas por más de **$80M COP** en la última hora.

El CTO les acaba de asignar la tarea: construir, en el tiempo que dura esta noche de picos de tráfico, un **motor de scoring de riesgo en tiempo real** capaz de:

- Evaluar transacciones al vuelo.
- Contener ataques de "card testing".
- Explicar sus decisiones — porque mañana Legal va a pedir cuentas de cada transacción bloqueada.

Van a construir **SentinelPay Risk Engine** usando un modelo de IA (**GLM 5.2**) como copiloto de desarrollo. Tienen el caso completo abajo, organizado en fases que se construyen una sobre otra: **no salten fases**, porque cada una es prerrequisito de la siguiente (igual que en producción, donde no puedes lanzar el modelo de scoring sin antes tener el pipeline de ingesta funcionando).

---

## ⏱ Línea de tiempo sugerida (80 minutos)

| Tiempo | Actividad |
| --- | --- |
| **0–8 min** | Leer el caso completo, definir arquitectura y stack con el equipo, primer prompt de planeación a la IA. |
| **8–30 min** | Fase 1 y Fase 2 (ingesta + reglas + velocity checks). |
| **30–50 min** | Fase 3 (scoring ponderado + resiliencia ante servicio externo). |
| **50–62 min** | Fase 4 (interfaz gráfica de verificación) . |
| **62–74 min** | Bonos (elegir 1 o 2, no todos) + pruebas de borde. |
| **74–80 min** | Cerrar bitácora de prompts, README y dependencias; repaso final de entregables. |

---

## 🎯 Objetivo general

Construir un servicio (**API o CLI**, a elección del equipo) que reciba transacciones y devuelva, para cada una:

- Un **score de riesgo** (0–100).
- Una **decisión** (`APPROVE` / `REVIEW` / `DECLINE`).
- Al menos **una razón explicable** de por qué se tomó esa decisión.

El sistema debe soportar **ráfagas de transacciones concurrentes** sin corromper su estado interno, y debe exponer una **interfaz gráfica sencilla** (Fase 4) para que cualquier persona — incluyendo los jueces — pueda ingresar una transacción a mano y ver el resultado sin tocar código ni usar Postman.

---

## 🧩 Fases de desarrollo

### FASE 1 · Ingesta y reglas base

Reciban transacciones con al menos: `id`, `card_id`, `merchant_id`, `amount`, `currency`, `country` (país registrado de la tarjeta), `ip_country` (país inferido de la IP), `device_id`, `ip`, `timestamp` (ISO 8601).

**Ejemplo de entrada:**

```json
{
  "id": "txn_00234",
  "card_id": "card_9F21",
  "merchant_id": "merch_petshop_bog",
  "amount": 850000,
  "currency": "COP",
  "country": "CO",
  "ip_country": "RU",
  "device_id": "dev_a19x",
  "ip": "185.220.101.14",
  "timestamp": "2024-11-28T04:58:12Z"
}
```

Implementen un endpoint/función `evaluate(transaction)` que aplique al menos **3 reglas estáticas**:

1. **Monto anómalo:** si `amount` supera 3 veces el promedio histórico de esa tarjeta → **+25 pts** al score.
2. **País distinto:** si `country` ≠ `ip_country` → **+30 pts** al score.
3. **Hora inusual:** transacciones entre 1:00 a.m. y 5:00 a.m. hora local del comercio → **+10 pts** al score.

- Cada regla debe poder **activarse/desactivarse** y aportar un **peso configurable** al score (ej. vía archivo de config o parámetros).
- **Persistencia en memoria** está bien (no se requiere base de datos externa).

> **Comportamiento esperado con el ejemplo de arriba:** tarjeta registrada en Colombia (CO) pero IP de Rusia (RU) a las 4:58 a.m. → se disparan la regla de país (+30) y hora inusual (+10) → **score parcial de fase 1 = 40**, aún sin contar señales de velocidad (fase 2).

---

### FASE 2 · Detección de "card testing" (ventanas deslizantes)

Los atacantes prueban muchas transacciones pequeñas en poco tiempo. Implementen:

- Un **rate limiter** por tarjeta y por dispositivo usando **ventana deslizante (sliding window)**, no ventana fija ingenua.
- **Regla de velocidad** (parámetros sugeridos):
  - Si una tarjeta supera **5 transacciones en 10 segundos** (configurable), el score sube **+40 pts**.
  - Si un mismo `device_id` intenta con **3 tarjetas distintas en 30 segundos**, **+50 pts**.
- Un mecanismo de **blocklist temporal**: tras superar el umbral de velocidad, la tarjeta/dispositivo queda bloqueado (todas sus transacciones futuras van directo a `DECLINE`) por, por ejemplo, **120 segundos**, con **expiración automática** — pasado ese tiempo, vuelve a evaluarse normalmente.

**Ejemplo de comportamiento esperado:** llegan 6 transacciones de `card_id: card_9F21` en 7 segundos, cada una por montos entre $5.000 y $15.000 COP (típico de "card testing", montos bajos para no llamar la atención). La transacción **#6** debe:

- Activar la regla de velocidad (**+40 pts**).
- Marcar esa tarjeta como bloqueada temporalmente.
- Devolver decisión `DECLINE` con razón `"velocity_limit_exceeded: 6 txns in 7s (limit: 5 in 10s)"`.
- Cualquier transacción **#7, #8...** de esa misma tarjeta durante los siguientes 120s debe rechazarse **inmediatamente sin re-evaluar reglas**, con razón `"card_temporarily_blocked"`.

---

### FASE 3 · Scoring ponderado + resiliencia

- Combinen todas las señales (fase 1 y 2) en un **score único ponderado**, con umbrales claros:
  - `APPROVE` (**< 40**)
  - `REVIEW` (**40–74**)
  - `DECLINE` (**≥ 75**)
- El score final **no debe superar 100** (definan cómo normalizan si varias reglas se disparan a la vez).
- Simulen una llamada a un servicio externo de autorización bancaria (`mock_bank_auth()`) que aleatoriamente falla o demora (timeout) — por ejemplo, **30% de probabilidad** de fallar o tardar >2s.
- Implementen un **circuit breaker**:
  - Si el servicio falla **3 veces seguidas**, el circuito se **"abre"** y deja de llamarlo por, por ejemplo, **15 segundos**, degradando el comportamiento de forma segura (ej: enviar a `REVIEW` en vez de fallar toda la transacción).
  - Pasado ese tiempo, el circuito pasa a **"semi-abierto"** e intenta de nuevo con una sola llamada de prueba.
- Cada respuesta debe incluir el **desglose** de por qué se llegó a ese score (qué reglas se activaron y con qué peso).

**Ejemplo de salida esperada** (para la transacción de ejemplo de la Fase 1, asumiendo que no hay señales de velocidad):

```json
{
  "transaction_id": "txn_00234",
  "score": 40,
  "decision": "REVIEW",
  "reasons": [
    { "rule": "country_mismatch", "weight": 30, "detail": "card_country=CO, ip_country=RU" },
    { "rule": "unusual_hour", "weight": 10, "detail": "04:58 local time" }
  ],
  "bank_auth_status": "circuit_open_degraded"
}
```

---

### FASE 4 · Interfaz gráfica de verificación 

Toda la lógica de las fases anteriores debe poder probarse **sin usar consola, curl ni Postman**. Construyan una interfaz gráfica sencilla (página web local, app de escritorio simple, o incluso un notebook con widgets interactivos — lo que el equipo prefiera) que permita:

- **Ingresar los datos** de una transacción mediante un formulario con campos para cada atributo (`card_id`, `amount`, `currency`, `country`, `ip_country`, `device_id`, `ip`) — no es necesario escribir JSON a mano.
- **Mostrar el resultado** de forma clara al enviar: score numérico, decisión (`APPROVE`/`REVIEW`/`DECLINE` — idealmente con color: verde/amarillo/rojo) y el desglose de razones que la generaron.
- **Permitir simular una ráfaga:** un botón o campo que dispare N transacciones seguidas con la misma tarjeta (por ejemplo, reenviando el mismo formulario 6 veces rápido), para que el jurado vea en vivo cómo el sistema detecta el "card testing" y bloquea la tarjeta sin necesidad de mirar logs de consola.


**Ejemplo de flujo esperado:** el juez abre la interfaz en el navegador, llena el formulario con los datos del ejemplo de la Fase 1, presiona **"Evaluar"** y ve en pantalla: `Score: 40 · REVIEW` junto con la lista de razones (`country_mismatch`, `unusual_hour`). Luego presiona **"Simular ráfaga (6x)"** con otra tarjeta y ve cómo las primeras 5 transacciones se aprueban/revisan normalmente y la 6ª sale en rojo como `DECLINE` — `velocity_limit_exceeded`.

---

## 💎 Requerimientos bono (puntos extra)

> Elijan estratégicamente — **no es necesario implementar todos**. Bien resuelto, un solo bono avanzado vale más que varios superficiales.

### Bono A — Detección de colusión por grafo (hasta +10 pts)
Modelen tarjetas, dispositivos e IPs como nodos de un grafo. Si detectan que múltiples `card_id` distintos comparten el mismo `device_id` o `ip` en una ventana corta de tiempo, márquenlo como posible **"ring" de fraude** y expliquen qué nodos están conectados y por qué.

### Bono B — Concurrencia segura (hasta +8 pts)
Demuestren (con una **prueba de carga/concurrencia real**, no solo afirmándolo) que su estructura de conteo de transacciones por tarjeta es segura ante N hilos/requests simultáneos evaluando la misma tarjeta al mismo tiempo, sin condiciones de carrera que subcuenten o sobrecuenten transacciones.

### Bono C — Explicabilidad exportable (hasta +6 pts)
Generen, para cada transacción en `DECLINE`, un **reporte estructurado (JSON)** apto para auditoría legal: reglas activadas, pesos, timestamp, y una **explicación en lenguaje natural** generada por la IA a partir de esos datos.

### Bono D — Suite de pruebas adversariales (hasta +6 pts)
Escriban un set de **pruebas automatizadas** que simule específicamente patrones de ataque (ráfaga de microtransacciones, spoofing de IP entre transacciones consecutivas, dispositivo reciclado entre tarjetas) y verifiquen que el sistema reacciona correctamente a cada patrón.

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
| **Funcionalidad core** (38 pts) | Fase 1: ingesta + reglas base funcionando y configurables (ver ejemplo Fase 1) | 10 |
| | Fase 2: ventana deslizante + blocklist con auto-expiración funcionando como en el ejemplo de comportamiento | 10 |
| | Fase 3: scoring ponderado + circuit breaker con degradación segura | 10 |
| | Umbrales de decisión (APPROVE/REVIEW/DECLINE) correctamente aplicados en casos de prueba | 8 |
| **Calidad técnica** (20 pts) | Arquitectura clara, modular, separación de responsabilidades | 11 |
| | Manejo de errores y casos borde (montos inválidos, timestamps futuros, etc.) | 9 |
| **Explicabilidad** (14 pts) | Cada decisión trae razones claras y trazables a reglas específicas, con formato tipo el ejemplo de salida | 14 |
| **Interfaz gráfica** (13 pts) | Permite ingresar los datos de una transacción por formulario (sin curl/Postman) y muestra score + decisión + razones | 8 |
| | Permite simular una ráfaga y visualizar en vivo el bloqueo por card testing | 5 |
| **Uso efectivo de IA** (15 pts) | Bitácora de prompts muestra iteración y pensamiento crítico, no copy-paste ciego | 10 |
| | Evidencia de que el equipo entendió y pudo explicar el código generado | 5 |
| **Subtotal base** | | **100** |
| **Bonos** | Bono A (grafo) + Bono B (concurrencia) + Bono C (auditoría) + Bono D (pruebas adversariales) | hasta **+30** |

> **Nota de calificación:** cada criterio se puntúa como fracción de su máximo (0%, 50% o 100% de cumplimiento) para mantener la evaluación objetiva y rápida — no hay que inventar escalas distintas por fila.

**Puntaje final** = subtotal base (máx. 100) + bonos (máx. 30) → escala final sobre **130**, normalizable a 100 si se requiere comparar contra otras hackathons del evento.
