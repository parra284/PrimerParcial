# Backend — Emergency Control

API Python que expone `POST /api/solve`. La guía completa de ejecución está en
[`../README.md`](../README.md); aquí solo lo propio del backend.

## Qué hay dentro de `src/`

| Paquete | Responsabilidad |
|---|---|
| `agent/` | **Modelo interno de IA**: estado ⟨pos, b, P, R, E, O⟩, acciones internas, modelo de transición con podas, prueba de meta y Uniform Cost Search con Graph Search. No importa FastAPI ni conoce el contrato visual. Solo Python estándar. |
| `contract/` | **Capa visual**: traduce cada acción interna a las cuatro operaciones de `CONTRATO.md` y audita que el costo emitido coincida con el del motor. Importa `agent`, nunca al revés. |
| `main.py` | FastAPI. Orquesta: `parse_scenario` → `solve` → `build_solve_response`. |
| `demo_plan.py`, `simulator.py` | Del repositorio base. El endpoint ya no usa `demo_plan`; `simulator.py` se usa en las pruebas para re-ejecutar el plan emitido. |

El diseño que implementa `agent/` está documentado en
[`../design.md`](../design.md).

## Instalar y correr

```bash
cd project/backend
python -m venv .venv
# Windows:      .\.venv\Scripts\Activate.ps1
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

uvicorn main:app --app-dir src --port 8000
```

Con recarga automática durante el desarrollo: añade `--reload`.

Comprobar: <http://127.0.0.1:8000/api/health> · API docs: <http://127.0.0.1:8000/docs>

> El puerto 8000 es el que espera el proxy del frontend (`vite.config.ts`).

## Usar el agente como librería

```bash
cd project/backend
python -c "import json,sys; sys.path.insert(0,'src'); from agent import parse_scenario, solve, format_plan; s=parse_scenario(json.load(open('../scenarios/ejemplo_minimo.json',encoding='utf-8'))); print(format_plan(s, solve(s)))"
```

## Pruebas

```bash
cd project/backend
python tests/run_entregable3.py    # los 5 casos de validación del enunciado
python tests/test_demo_plan.py     # plan artesanal del repositorio base
```

No se «arregla» `scenario.json` (capacidad, batería, zonas) para que UCS
termine: la formulación correcta está en `Applicable`. Ver `../design.md`.
