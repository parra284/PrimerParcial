"""Armado de la respuesta de `POST /api/solve` (CONTRATO.md §2).

Formato fijo exigido por el contrato::

    { "solution_found": bool, "total_cost": int, "steps": [...], "message": str }

A esos cuatro campos se añaden dos **opcionales** que el banco de pruebas ignora
y que sirven para visualizar e inspeccionar la ejecución:

* `trace`  — estado del mundo tras cada paso (zona, batería, energía gastada,
  inventario, puertas, paneles, estaciones).
* `search` — algoritmo y métricas de la búsqueda (nodos expandidos, tiempo...).
"""

from __future__ import annotations

from typing import Any

from agent import SearchResult, SearchStatus, WorldSpec

from .translate import build_trace, steps_to_dicts, translate_plan


def build_solve_response(
    spec: WorldSpec, result: SearchResult, *, include_trace: bool = True
) -> dict[str, Any]:
    """Traduce un `SearchResult` del motor a la respuesta del endpoint."""

    search_info = {
        "algorithm": "Uniform Cost Search (Graph Search) con dominancia de batería",
        "status": result.status.value,
        "internal_actions": len(result.plan),
        **_stats_to_dict(result),
    }

    if result.status is not SearchStatus.SUCCESS:
        # FAILURE (OPEN vacío) o LIMIT_REACHED (límite opcional de recursos).
        # En ambos casos el contrato exige steps vacío; total_cost va en 0
        # porque el frontend lo tipa como número.
        return {
            "solution_found": False,
            "total_cost": 0,
            "steps": [],
            "message": result.message,
            "trace": [],
            "search": search_info,
        }

    steps = translate_plan(spec, result.plan, expected_cost=result.total_cost)
    response: dict[str, Any] = {
        "solution_found": True,
        "total_cost": result.total_cost,
        "steps": steps_to_dicts(steps),
        "message": (
            f"Plan óptimo: {len(result.plan)} acciones internas → "
            f"{len(steps)} operaciones visuales, costo total {result.total_cost}."
        ),
        "search": search_info,
    }
    if include_trace:
        response["trace"] = build_trace(spec, result.plan, result.states)
    return response


def _stats_to_dict(result: SearchResult) -> dict[str, Any]:
    stats = result.stats
    return {
        "expanded": stats.expanded,
        "generated": stats.generated,
        "pruned_dominated": stats.dominated_on_pop + stats.dominated_on_generation,
        "max_open_size": stats.max_open_size,
        "closed_size": stats.closed_size,
        "elapsed_seconds": round(stats.elapsed_seconds, 3),
    }
