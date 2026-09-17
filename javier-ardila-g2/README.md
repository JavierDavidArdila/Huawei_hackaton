# FlowMatch Assignment Engine - Reto 2

## Equipo
- Javier Ardila - Grupo 2

## Descripción
Motor de asignación en tiempo real para QuickBite, una app de domicilios. Decide a qué repartidor asignar cada pedido durante hora pico, respetando límites de capacidad, prioridades, control de ráfagas y optimización de costo.

## Arquitectura

### Servicios desacoplados (Docker Compose)

```
┌─────────────────────────────────────────────────────┐
│                   docker-compose                     │
│                                                      │
│  ┌──────────────────┐    ┌──────────────────┐       │
│  │  assignment-engine│    │  pricing-service  │       │
│  │  (FastAPI :8000)  │───▶│  (FastAPI :8001)  │       │
│  │                   │    │  mock con 30%     │       │
│  │  • Fase 1: reglas │    │  fallo/timeout    │       │
│  │  • Fase 2: ráfagas│    └──────────────────┘       │
│  │  • Fase 3: costo  │                               │
│  │  • Circuit breaker│    ┌──────────────────┐       │
│  │  • Estado thread  │    │   frontend        │       │
│  │    safe (Locks)   │    │  (nginx :8080)    │       │
│  │  • API REST       │◀───│  HTML/JS/CSS      │       │
│  └──────────────────┘    └──────────────────┘       │
└─────────────────────────────────────────────────────┘
```

| Contenedor | Puerto | Responsabilidad |
|---|---|---|
| assignment-engine | 8000 | Lógica de asignación (Fases 1-3), estado thread-safe, API REST, circuit breaker |
| pricing-service | 8001 | Servicio externo simulado de tarifa dinámica (30% fallo/timeout) |
| frontend | 8080 | Interfaz gráfica (formulario, colores, botón ráfaga) |

### Estructura interna del assignment-engine

```
app/
├── main.py                 # FastAPI app + endpoints REST
├── models.py               # Pydantic: Order, Courier, AssignmentResult
├── config.py               # Reglas activables/desactivables
├── engine/
│   ├── assigner.py         # Fase 1: same_zone, capacity, least_loaded
│   ├── burst_control.py    # Fase 2: sliding window, zone balance, contención
│   ├── optimizer.py        # Fase 3: minimizar costo
│   └── batch_optimizer.py  # Bono A: algoritmo húngaro
├── resilience/
│   ├── circuit_breaker.py  # Circuit breaker (CLOSED/OPEN/HALF_OPEN)
│   └── pricing_client.py   # Cliente HTTP con circuit breaker
├── state/
│   ├── courier_state.py    # Estado thread-safe (asyncio.Lock)
│   ├── wait_queue.py       # Cola de espera + contención
│   └── rate_limiter.py     # Sliding window rate limiter
└── explainability/
    └── reporter.py         # Bono C: reporte JSON + explicación natural
```

## Decisiones de diseño

1. **FastAPI + asyncio**: Elegido por su soporte nativo para async, validación con Pydantic, y facilidad para thread-safety con `asyncio.Lock`.
2. **Estado en memoria con Locks**: `courier_state`, `wait_queue` y `rate_limiter` usan `asyncio.Lock` para garantizar thread-safety ante requests concurrentes (Bono B).
3. **Sliding window con deque**: El rate limiter usa `collections.deque` para implementar ventana deslizante eficientemente.
4. **Circuit breaker desacoplado**: El circuit breaker vive en el assignment-engine y protege contra fallos del pricing-service. Cuando está abierto, usa tarifa base fija (degradación segura).
5. **Configuración dinámica**: Todas las reglas son activables/desactivables via API (`PUT /config`).
6. **Algoritmo húngaro para lotes**: Bono A usa `scipy.optimize.linear_sum_assignment` para emparejamiento óptimo pedido↔repartidor.

## Cómo correr el proyecto

### Opción 1: Docker Compose (recomendado)

```bash
cd codigo
docker compose up --build
```

- Frontend: http://localhost:8080
- API: http://localhost:8000
- Pricing Service: http://localhost:8001

### Opción 2: Sin Docker (desarrollo local)

```bash
# Terminal 1 - Pricing service
cd codigo/pricing-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8001

# Terminal 2 - Assignment engine
cd codigo/assignment-engine
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000

# Terminal 3 - Frontend (servidor estático)
cd codigo/frontend
python -m http.server 8080
# Abrir http://localhost:8080
```

### Correr tests

```bash
cd codigo/assignment-engine
source .venv/bin/activate
python -m pytest tests/ -v
```

## Endpoints de la API

| Método | Path | Descripción |
|---|---|---|
| POST | /assign | Asignar un pedido (Fases 1-3) |
| POST | /assign-batch | Asignar lote de pedidos (Bono A - óptimo) |
| POST | /assign-batch/compare | Comparar greedy vs óptimo |
| GET | /couriers | Estado actual de repartidores |
| POST | /couriers/reset | Resetear estado |
| POST | /couriers/init | Inicializar repartidores |
| GET | /config | Ver configuración de reglas |
| PUT | /config | Activar/desactivar reglas |
| GET | /explanation/{order_id} | Explicación de un REJECTED (Bono C) |
| GET | /explanations/rejected | Todas las explicaciones de rechazos |
| GET | /queue | Estado de la cola de espera |
| GET | /health | Health check + estado del circuit breaker |

## Fases implementadas

### Fase 1 - Asignación base por prioridad
- 3 reglas configurables: misma zona, capacidad, menor carga
- Estado en memoria, actualización de `active_orders` al asignar
- Si todos llenos → `QUEUED`

### Fase 2 - Control de ráfagas
- Sliding window rate limiter por repartidor ( configurable: máx 3 pedidos en 10s)
- Balanceo de zona: si zona saturada, busca en zonas vecinas
- Modo contención temporal: 3 pedidos consecutivos con todos llenos + cola creciendo → `REJECTED` por 120s (auto-expiración). Express sigue encolándose.

### Fase 3 - Optimización de costo + resiliencia
- Minimiza costo entre repartidores válidos (distancia × tarifa)
- Pricing service simulado con 30% de fallo/timeout
- Circuit breaker: 3 fallos → OPEN 15s → HALF_OPEN → reintento
- Degradación segura: tarifa base fija cuando circuito abierto

### Fase 4 - Interfaz gráfica
- Formulario para ingresar pedidos sin JSON
- Resultados con colores: verde (ASSIGNED), amarillo (QUEUED), rojo (REJECTED)
- Botón "Simular ráfaga (6x)" para ver contención en vivo
- Tabla editable de repartidores
- Panel de configuración de reglas (checkboxes)
- Panel de estado del sistema (circuit breaker, cola, contención)

## Bonos implementados

### Bono A - Optimización global por lotes (+10 pts)
- `batch_optimizer.py` con algoritmo húngaro (`scipy.optimize.linear_sum_assignment`)
- Endpoint `POST /assign-batch` para asignación óptima conjunta
- Endpoint `POST /assign-batch/compare` para comparar greedy vs óptimo
- Matriz de costo: distancia × tarifa + penalización de zona + penalización de carga

### Bono B - Concurrencia segura (+8 pts)
- `asyncio.Lock` en `courier_state`, `wait_queue` y `rate_limiter`
- `test_concurrency.py`: 3 pruebas con requests simultáneos (`asyncio.gather`)
  - 10 requests concurrentes a 1 courier (max_capacity=2) → nunca excede 2
  - 10 requests a 5 couriers (max_capacity=1) → nunca excede 1 por courier
  - 20 requests a 2 couriers (max_capacity=3) → total nunca excede 6

### Bono C - Explicabilidad exportable (+6 pts)
- `reporter.py` genera reporte JSON para cada REJECTED
- Incluye: reglas activadas, estado de couriers, timestamp, explicación en lenguaje natural
- Endpoint `GET /explanation/{order_id}` y `GET /explanations/rejected`

### Bono D - Suite de pruebas de escenarios extremos (+6 pts)
- `test_extreme.py`: 8 pruebas para escenarios críticos
  - Ráfaga a una sola zona
  - Todos los repartidores llenos de golpe
  - Avalancha de pedidos express
  - Distancia negativa (422)
  - Prioridad inválida (422)
  - Sin repartidores (400)
  - Nunca excede capacidad (15 pedidos, 3 couriers max=2)
  - Expiración de contención permite orders de nuevo

## Resultados de tests

```
29 passed in 6.72s
```

- test_phase1.py: 7 tests (asignación base)
- test_phase2.py: 5 tests (ráfagas + contención)
- test_phase3.py: 6 tests (circuit breaker + optimizer)
- test_concurrency.py: 3 tests (Bono B)
- test_extreme.py: 8 tests (Bono D)
