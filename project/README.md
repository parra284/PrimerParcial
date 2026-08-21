# Proyecto — Emergency Control

Planificador autónomo de operaciones críticas: un agente de búsqueda clásica
(UCS con Graph Search) resuelve la misión, un backend FastAPI lo expone en
`POST /api/solve` y un frontend React + React Three Fiber reproduce el plan en
una simulación 3D.

- Diseño de IA: [`design.md`](design.md)
- Enunciado: [`../README.MD`](../README.MD) · Reglas del mundo: [`../CONTRATO.md`](../CONTRATO.md)

**Guía de ejecución (Entregable 4).** Todo lo que sigue está probado en este
repositorio; no hace falta configurar nada más.

---

## Estructura

```text
project/
├── frontend/                 React + R3F — simulación 3D voxel
│   └── src/
│       ├── lib/api.ts        llama a POST /api/solve y anima el plan
│       ├── lib/executor.ts   re-ejecuta cada paso contra su propio simulador
│       └── ui/HUD.tsx        batería, payload, costo y log de ejecución
├── backend/
│   ├── src/
│   │   ├── agent/            MODELO INTERNO DE IA (no conoce HTTP ni frontend)
│   │   │   ├── constants.py  sentinelas de O, enums de acciones
│   │   │   ├── world.py      WorldSpec: mapa, requisitos, costos (parse_scenario)
│   │   │   ├── state.py      s = <pos, b, P, R, E, O>, canonicalización, meta
│   │   │   ├── actions.py    acciones internas del agente
│   │   │   ├── transition.py Applicable(s), Result(s,a), podas
│   │   │   ├── search.py     UCS + Graph Search + dominancia de batería
│   │   │   └── solver.py     solve_scenario / replay_plan / format_plan
│   │   ├── contract/         CAPA VISUAL (traduce el plan interno al contrato)
│   │   │   ├── visual.py     vocabulario cerrado + auditoría de costos
│   │   │   ├── translate.py  acción interna → 1..n operaciones visuales + traza
│   │   │   └── response.py   respuesta de /api/solve
│   │   ├── main.py           FastAPI: parse → solve → traducir
│   │   ├── demo_plan.py      plan artesanal del repo base (ya no lo usa el endpoint)
│   │   └── simulator.py      mini-simulador del repo base (se usa en pruebas)
│   └── tests/                validación (Entregable 3)
├── scenarios/                instancias JSON
├── design.md
└── README.md
```

La dependencia va en un solo sentido: `contract` importa `agent`; `agent` no
sabe que existe el contrato visual. La capa visual no decide nada de la lógica
del agente: solo reexpresa el plan ya calculado.

---

## Requisitos

| Herramienta | Mínimo | Probado con |
|---|---|---|
| Python | 3.10 | 3.13.7 |
| pip | cualquiera reciente | 25.2 |
| Node.js | 20 LTS (Vite 6) | 22.18.0 |
| npm | 10 | 10.9.3 |

Dependencias del backend: `fastapi` y `uvicorn[standard]` (en
`backend/requirements.txt`). El agente en sí es **Python estándar**: no usa
ninguna librería externa.

---

## 1. Instalar dependencias

### Backend

```bash
cd project/backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Windows Git Bash:  source .venv/Scripts/activate
# macOS / Linux:     source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend

```bash
cd project/frontend
npm install
```

---

## 2. Iniciar el backend

```bash
cd project/backend
uvicorn main:app --app-dir src --port 8000
```

Comprobar: <http://127.0.0.1:8000/api/health> → `{"status":"ok"}`
Documentación interactiva de la API: <http://127.0.0.1:8000/docs>

> El puerto **8000** no es opcional si vas a usar el frontend: `vite.config.ts`
> redirige `/api` a `http://127.0.0.1:8000`. Añade `--reload` si vas a editar
> código.

---

## 3. Iniciar el frontend

En una **segunda terminal**, con el backend ya corriendo:

```bash
cd project/frontend
npm run dev
```

Abrir <http://localhost:5173>.

---

## 4. Probar una misión

### Desde la interfaz

Pulsa **▶ EXECUTE PLAN**. El frontend envía `scenarios/scenario.json` a
`/api/solve`, recibe el plan y lo reproduce casilla a casilla. **La primera
respuesta tarda unos 13 segundos**: el agente está explorando ~690 000 nodos
para garantizar el plan óptimo. No está colgado.

### Desde la terminal

```bash
# Git Bash / macOS / Linux
cd project
curl -s -X POST http://127.0.0.1:8000/api/solve \
  -H "Content-Type: application/json" \
  --data @scenarios/ejemplo_minimo.json
```

```powershell
# Windows PowerShell (curl es un alias de Invoke-WebRequest: usa este comando)
cd project
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/solve -Method Post `
  -ContentType 'application/json' -InFile scenarios/ejemplo_minimo.json
```

Cambia el archivo por `scenarios/scenario.json` para la misión completa.

### Parámetros opcionales del endpoint

| Query param | Efecto |
|---|---|
| `?node_limit=N` | Corta la búsqueda tras N nodos expandidos y responde `LIMIT_REACHED`. |
| `?time_limit=S` | Igual, pero por segundos. |
| `?trace=false` | Omite la traza estado a estado (respuesta más liviana). |

Sin ellos la búsqueda es exacta y termina por sí sola: el espacio de estados es
finito y toda acción cuesta ≥ 1.

### Otros endpoints

| Endpoint | Para qué |
|---|---|
| `GET /api/health` | Comprobar que el backend está vivo. |
| `GET /api/scenario` | Devuelve el `scenario.json` del repositorio. |
| `POST /api/solve` | Planificar. Si el body va vacío, usa `scenario.json`. |

---

## 5. Ejecutar el agente sin levantar nada

El motor se puede usar directamente como librería:

```bash
cd project/backend
python -c "import json,sys; sys.path.insert(0,'src'); from agent import parse_scenario, solve, format_plan; s=parse_scenario(json.load(open('../scenarios/ejemplo_minimo.json',encoding='utf-8'))); print(format_plan(s, solve(s)))"
```

Salida real:

```text
SUCCESS — 8 acciones, costo total 14
  s0: pos=Z1 b=20 inv=- doors=- panels=- stations=-
    1. PICKUP KEY1 (costo 1)                          | pos=Z1 b=19 inv=['KEY1'] ...
    2. PICKUP MULTITOOL (costo 1)                     | pos=Z1 b=18 inv=['KEY1', 'MULTITOOL'] ...
    3. OPEN_DOOR DOOR1 [KEY1] (costo 2)               | pos=Z1 b=16 doors=['DOOR1'] ...
    4. DROP KEY1 (costo 1)                            | pos=Z1 b=15 inv=['MULTITOOL'] ...
    5. PICKUP FUSE (costo 1)                          | pos=Z1 b=14 inv=['MULTITOOL', 'FUSE'] ...
    6. MOVE Z1 -> Z2 (costo 4)                        | pos=Z2 b=10 ...
    7. REPAIR PANEL_A [MULTITOOL + FUSE] (costo 2)    | pos=Z2 b=8  panels=['PANEL_A'] ...
    8. ACTIVATE GENERATOR (costo 2)                   | pos=Z2 b=6  stations=['GENERATOR'] ...
  meta alcanzada: True
```

Esas son las **acciones internas** del agente. El endpoint las traduce al
contrato visual antes de responder.

---

## 6. Ejemplo mínimo de entrada y salida

### Entrada — `scenarios/ejemplo_minimo.json`

Misma estructura que `scenario.json`, reducida a dos zonas para que responda en
menos de un segundo. Capacidad 2, así que el robot debe soltar la llave ya usada
para poder cargar herramienta y material.

```json
{
  "robot": { "start": "Z1", "battery_max": 20, "battery_start": 20, "cargo_capacity": 2 },
  "zones": [
    { "id": "Z1", "name": "CONTROL", "recharge": false },
    { "id": "Z2", "name": "GENERATOR_BAY", "recharge": false }
  ],
  "corridors": [
    { "from": "Z1", "to": "Z2", "cost": 4, "door": "DOOR1" },
    { "from": "Z2", "to": "Z1", "cost": 4, "door": "DOOR1" }
  ],
  "doors": [
    { "id": "DOOR1", "color": "cyan", "key": "KEY1", "state": "CLOSED", "between": ["Z1", "Z2"] }
  ],
  "keys":      [{ "id": "KEY1", "color": "cyan", "zone": "Z1", "weight": 1 }],
  "tools":     [{ "id": "MULTITOOL", "repairs": "ELECTRICAL", "zone": "Z1", "weight": 1 }],
  "materials": [{ "type": "FUSE", "zone": "Z1", "count": 1, "weight": 1 }],
  "panels": [
    { "id": "PANEL_A", "zone": "Z2", "damage": "ELECTRICAL",
      "requires": { "tool": "MULTITOOL", "material": "FUSE" }, "state": "DAMAGED" }
  ],
  "stations": [
    { "id": "GENERATOR", "kind": "generator", "zone": "Z2", "state": "OFFLINE",
      "requires": { "panels_ok": ["PANEL_A"] } }
  ],
  "chargers": [],
  "goal": { "stations_online": ["GENERATOR"] },
  "action_costs": { "pickup": 1, "drop": 1, "interact": 2, "recharge": 3 }
}
```

`layout` solo lo necesita el visor 3D, que siempre carga `scenario.json`; para
la API es opcional.

### Salida — respuesta real del endpoint (HTTP 200, 0,06 s)

```json
{
  "solution_found": true,
  "total_cost": 14,
  "steps": [
    { "op": "PICKUP", "item": "KEY1", "cost": 1 },
    { "op": "PICKUP", "item": "MULTITOOL", "cost": 1 },
    { "op": "INTERACT", "target": "DOOR1", "action": "OPEN_DOOR", "cost": 2 },
    { "op": "DROP", "item": "KEY1", "cost": 1 },
    { "op": "PICKUP", "item": "FUSE", "cost": 1 },
    { "op": "MOVE", "from": "Z1", "to": "Z2", "cost": 4 },
    { "op": "INTERACT", "target": "PANEL_A", "action": "REPAIR", "cost": 2, "consumes": "FUSE" },
    { "op": "INTERACT", "target": "GENERATOR", "action": "ACTIVATE", "cost": 2 }
  ],
  "message": "Plan óptimo: 8 acciones internas → 8 operaciones visuales, costo total 14.",
  "trace": [
    { "step": 0, "zone": "Z1", "battery": 20, "energy_spent": 0, "payload": [],
      "doors": { "DOOR1": "CLOSED" }, "panels": { "PANEL_A": "DAMAGED" },
      "stations": { "GENERATOR": "OFFLINE" }, "goal_reached": false },
    "… un elemento por paso …",
    { "step": 8, "zone": "Z2", "battery": 6, "energy_spent": 14, "payload": ["MULTITOOL"],
      "doors": { "DOOR1": "OPEN" }, "panels": { "PANEL_A": "OK" },
      "stations": { "GENERATOR": "ONLINE" }, "goal_reached": true }
  ],
  "search": {
    "algorithm": "Uniform Cost Search (Graph Search) con dominancia de batería",
    "status": "SUCCESS", "internal_actions": 8, "expanded": 20, "generated": 39,
    "pruned_dominated": 18, "max_open_size": 6, "closed_size": 21,
    "elapsed_seconds": 0.001
  }
}
```

Con `scenarios/scenario.json` la respuesta tiene la misma forma:
`solution_found: true`, **`total_cost: 80`**, 35 pasos y 36 elementos de traza,
en ~13 s.

---

## 7. Interpretar el resultado

### Campos de la respuesta

| Campo | Qué significa |
|---|---|
| `solution_found` | `true` si existe plan. `false` es el `FAILURE` del enunciado. |
| `total_cost` | g(n) del plan: **batería total consumida**, no número de pasos. Es la suma exacta de los `cost` de `steps`. |
| `steps` | El plan traducido al contrato cerrado de `CONTRATO.md`. |
| `message` | Resumen legible; en caso de fallo, el motivo. |
| `trace` | *(extra)* Estado del mundo tras cada paso. `step` es el número de operaciones ejecutadas, así que `trace[k]` es el estado justo después de `steps[k-1]`. |
| `search` | *(extra)* Algoritmo y métricas: nodos expandidos, generados, podados por dominancia, tamaño de `CLOSED`, segundos. |

`trace` y `search` son añadidos opcionales para visualizar y auditar; el banco
de pruebas solo necesita los cuatro primeros campos.

### Las operaciones del plan

Solo existen cuatro, y las cuatro acciones operativas viajan dentro de
`INTERACT` (CONTRATO.md §3):

| Paso | Lectura |
|---|---|
| `{"op":"MOVE","from":"Z1","to":"Z2","cost":4}` | Cruzar el corredor Z1→Z2; cuesta lo que diga ese corredor. |
| `{"op":"PICKUP","item":"KEY1","cost":1}` | Recoger del suelo de la zona actual. Materiales van por **tipo** (`FUSE`), llaves y herramientas por **id**. |
| `{"op":"DROP","item":"KEY1","cost":1}` | Soltar para hacer hueco. Solo aparece bajo presión de carga. |
| `{"op":"INTERACT","target":"DOOR1","action":"OPEN_DOOR","cost":2}` | Abrir puerta (exige la llave en el payload). |
| `{"op":"INTERACT","target":"PANEL_A","action":"REPAIR","consumes":"FUSE","cost":2}` | Reparar panel: consume el material, conserva la herramienta. |
| `{"op":"INTERACT","target":"GENERATOR","action":"ACTIVATE","cost":2}` | Activar estación (sus paneles y estaciones previas ya deben estar listos). |
| `{"op":"INTERACT","target":"CHARGER_1","action":"RECHARGE","cost":3}` | Recargar al máximo; el costo se paga antes. |

### En la interfaz

- **POWER CORE**: batería actual sobre la máxima.
- **PAYLOAD**: una casilla por unidad de capacidad de carga.
- **ENERGY COST**: energía gastada hasta el paso actual y, debajo, el costo
  total del plan. Al terminar deben coincidir.
- **EXECUTION LOG**: `STEP i/n` y una línea por paso. El frontend **no confía en
  el plan**: re-ejecuta cada paso contra su propio simulador, así que una línea
  roja significa que el paso violó una regla del mundo.
- Cierre esperado: `[***] MISSION COMPLETE — all stations ONLINE (spent 80)`.

### Cuando no hay solución

```json
{ "solution_found": false, "total_cost": 0, "steps": [],
  "message": "FAILURE: OPEN se vació sin alcanzar la meta; la misión es imposible.",
  "trace": [] }
```

El frontend lo muestra como `[---] FAILURE: ...`. Hay dos motivos posibles y el
campo `search.status` los distingue:

- `FAILURE` — `OPEN` se vació: la misión es **demostrablemente imposible**.
- `LIMIT_REACHED` — se agotó un `node_limit`/`time_limit` que tú pediste; no
  dice nada sobre si existe solución.

Un escenario mal formado (zona inexistente, costo 0, etc.) no es un `FAILURE`:
devuelve **HTTP 400** con el detalle, por ejemplo
`{"detail":"Escenario inválido: corredor Z1->ZONA_FANTASMA: zona desconocida"}`.

---

## 8. Ejecutar las pruebas

### Validación del agente (Entregable 3)

```bash
cd project/backend
python tests/run_entregable3.py
```

Los cinco casos del enunciado, contra el motor de búsqueda (no contra HTTP):

```text
  PASA  Caso 1 — Estados equivalentes            0.00s
  PASA  Caso 2 — Información relevante           0.00s
  PASA  Caso 3 — Costos diferentes              19.75s
  PASA  Caso 4 — Sin solución                    2.35s
  PASA  Caso 5 — Rutas alternativas              0.00s

  5/5 casos pasan (22.11s en total)
```

Cada caso corre también por separado, por ejemplo:

```bash
python tests/test_caso4_sin_solucion.py
```

Los 19,75 s del Caso 3 son la resolución completa de `scenario.json`; el Caso 5
reutiliza ese resultado cacheado. Son funciones `test_*` con `assert`, así que
`pytest tests/` también las recoge si prefieres instalarlo (no viene en
`requirements.txt`).

### Plan demo del repositorio base

```bash
cd project/backend
python tests/test_demo_plan.py
```

---

## 9. Escenarios disponibles

| Archivo | Para qué |
|---|---|
| `scenarios/scenario.json` | Misión oficial de la demo. Es lo que carga el frontend. |
| `scenarios/ejemplo_minimo.json` | Instancia mínima para probar la API en <1 s. |
| `scenarios/caso2_bateria_relevante.json` | Prueba: la batería distingue estados. |
| `scenarios/caso3_costo_vs_pasos.json` | Prueba: menos acciones ≠ menor costo. |
| `scenarios/caso4_dependencia_circular.json` | Prueba: FAILURE tras agotar el espacio. |
| `scenarios/caso4_bateria_insuficiente.json` | Prueba: FAILURE inmediato. |
| `scenarios/caso5_rutas_alternativas.json` | Prueba: se conserva la ruta barata. |

Los archivos `caso*` y `ejemplo_minimo` no traen `layout`: son instancias para
el motor y la API, no para el visor 3D. Detalles en
[`scenarios/README.md`](scenarios/README.md).

---

## 10. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `EXECUTE PLAN` no responde durante ~13 s | Normal: es la búsqueda óptima sobre `scenario.json`. El log muestra `Requesting plan...` mientras tanto. |
| `API ERROR: 500` o `fetch failed` en el log | El backend no está corriendo, o no está en el puerto 8000 (el proxy de Vite apunta ahí). |
| `[Errno 10048] ... solo se permite un uso de cada dirección de socket` | Ya hay algo escuchando en el 8000. Cierra el proceso anterior o levanta con `--port 8001` (y ajusta el proxy en `vite.config.ts`). |
| `ModuleNotFoundError: No module named 'agent'` | Falta `--app-dir src`, o estás lanzando uvicorn desde otra carpeta. |
| Acentos rotos en la consola de Windows | `set PYTHONIOENCODING=utf-8` antes de correr las pruebas. |

---

## Contrato visual vs. agente

La versión oficial y completa del contrato está en
[`../CONTRATO.md`](../CONTRATO.md), que forma parte del enunciado.

El enunciado fija **4 operaciones visuales** que el frontend entiende:

```text
MOVE | PICKUP | DROP | INTERACT
```

`REPAIR`, `ACTIVATE`, `OPEN_DOOR` y `RECHARGE` **no son ops del plan de alto
nivel**: son el campo `action` dentro de un paso `INTERACT`.

- **Agente:** modela sus acciones internas (`MOVE`, `PICKUP`, `DROP`,
  `OPEN_DOOR`, `REPAIR`, `ACTIVATE`, `RECHARGE`) en `backend/src/agent/`.
- **Traducción:** `backend/src/contract/` reexpresa cada acción interna como una
  o varias operaciones visuales y audita que el costo emitido coincida con el
  del motor, paso a paso y en total.
- **Frontend / banco de pruebas:** solo ejecuta esas 4 ops.

Así no hay contradicción: la capa visual no define la IA; solo anima el plan ya
traducido.

> Sobre `DROP`: el contrato lo permite en cualquier zona, pero el agente solo lo
> **genera** cuando el inventario no da para recoger un objeto relevante que
> está en esa zona. Restringir qué `DROP` se generan sin perder el plan óptimo
> es parte del diseño del agente, y está justificado en
> [`design.md`](design.md). No se "arregla" subiendo `cargo_capacity` en
> `scenario.json` ni apagando la batería.
