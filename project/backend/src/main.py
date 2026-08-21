"""FastAPI backend — Emergency Control.

`POST /api/solve` conecta las dos capas sin mezclarlas:

    escenario JSON
        → agent.parse_scenario   (modelo interno de IA)
        → agent.solve            (UCS + Graph Search)
        → contract.build_solve_response  (traducción al contrato visual)
        → respuesta JSON

El endpoint no contiene lógica de búsqueda ni conoce el vocabulario visual: solo
orquesta. La búsqueda vive en `agent/` y la traducción en `contract/`.
"""

from __future__ import annotations

import gc
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from agent import ScenarioError, parse_scenario, solve
from contract import ContractError, TranslationError, build_solve_response

app = FastAPI(title="Emergency Control API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCENARIO_PATH = Path(__file__).resolve().parents[2] / "scenarios" / "scenario.json"


def _load_default_scenario() -> dict[str, Any]:
    with SCENARIO_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@contextmanager
def _gc_paused() -> Iterator[None]:
    """Pausa el recolector de basura mientras corre la búsqueda.

    UCS crea millones de nodos, estados y acciones que **no forman ciclos**
    (tuplas y cadenas de padres), así que el conteo de referencias basta para
    liberarlos. Con el recolector activo, cada colección generacional recorre
    todo el montón vivo (`OPEN` + `CLOSED`) y en un proceso de servidor eso
    llega a triplicar el tiempo de respuesta. Es una decisión de la capa de
    servicio: el motor de búsqueda no se toca.
    """

    was_enabled = gc.isenabled()
    if was_enabled:
        gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()
            gc.collect()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/scenario")
def get_scenario() -> dict[str, Any]:
    return _load_default_scenario()


@app.post("/api/solve")
def solve_endpoint(
    scenario: dict[str, Any] | None = Body(default=None),
    node_limit: int | None = Query(
        default=None,
        description="Tope opcional de nodos expandidos. Sin él la búsqueda es exacta.",
    ),
    time_limit: float | None = Query(
        default=None,
        description="Tope opcional en segundos. Sin él la búsqueda es exacta.",
    ),
    trace: bool = Query(default=True, description="Incluir la traza estado a estado."),
) -> dict[str, Any]:
    """Planifica la misión y devuelve el plan ya traducido al contrato visual.

    Respuesta (CONTRATO.md §2)::

        { "solution_found": bool, "total_cost": int, "steps": [...],
          "message": str, "trace": [...], "search": {...} }

    `trace` y `search` son añadidos opcionales para la visualización y la
    depuración; el banco de pruebas solo necesita los cuatro primeros campos.

    Sin solución ⟹ `solution_found: false` y `steps: []`. La búsqueda termina
    siempre por sí sola (el espacio de estados es finito y todo costo es ≥ 1);
    `node_limit` y `time_limit` son cinturones de seguridad opcionales.
    """

    data = scenario if scenario else _load_default_scenario()

    try:
        spec = parse_scenario(data)
    except ScenarioError as exc:
        raise HTTPException(status_code=400, detail=f"Escenario inválido: {exc}") from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Escenario ilegible: {exc}") from exc

    with _gc_paused():
        result = solve(spec, node_limit=node_limit, time_limit=time_limit)

    try:
        return build_solve_response(spec, result, include_trace=trace)
    except (ContractError, TranslationError) as exc:
        # El plan interno es válido pero no pudo emitirse dentro del contrato:
        # es un fallo del backend, no del escenario.
        raise HTTPException(status_code=500, detail=f"Error de traducción: {exc}") from exc
