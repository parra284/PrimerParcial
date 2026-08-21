"""Punto de entrada del modelo interno: escenario → plan óptimo interno.

Referencia: `project/design.md` — §Estrategia de búsqueda.

`solve_scenario` recibe el escenario (zonas, corredores, puertas, paneles,
estaciones, cargadores, objetos, posición inicial, costos) y devuelve un
`SearchResult` con:

* `solution_found` / `status`;
* `plan`: la secuencia de **acciones internas** del plan de menor costo;
* `total_cost`: g(n) del plan (consumo total de batería);
* `states`: la traza de estados s₀ … s_meta, útil para depurar y, más adelante,
  para la capa de traducción visual.

Si no hay solución devuelve `SearchStatus.FAILURE` con `plan=()` y
`total_cost=None`. Nunca lanza una excepción por «no encontré nada» ni entra en
un bucle sin condición de salida.
"""

from __future__ import annotations

from typing import Any, Mapping

from .actions import Action
from .search import SearchResult, SearchStatus, uniform_cost_search
from .state import State, describe_state, initial_state, is_goal
from .transition import result as apply_action
from .world import WorldSpec, parse_scenario


def solve_scenario(
    scenario: Mapping[str, Any],
    *,
    node_limit: int | None = None,
    time_limit: float | None = None,
) -> SearchResult:
    """Resuelve una instancia completa con UCS + Graph Search."""

    spec = parse_scenario(scenario)
    return solve(spec, node_limit=node_limit, time_limit=time_limit)


def solve(
    spec: WorldSpec,
    *,
    node_limit: int | None = None,
    time_limit: float | None = None,
) -> SearchResult:
    """Igual que `solve_scenario` pero sobre un `WorldSpec` ya parseado."""

    if not spec.goal_stations:
        # Meta vacía: s₀ ya la satisface trivialmente.
        return SearchResult(
            status=SearchStatus.SUCCESS,
            plan=(),
            total_cost=0,
            states=(initial_state(spec),),
            message="La meta no exige ninguna estación: el estado inicial ya es meta.",
        )
    return uniform_cost_search(spec, node_limit=node_limit, time_limit=time_limit)


# ---------------------------------------------------------------------------
# Verificación / depuración del modelo interno
# ---------------------------------------------------------------------------


def replay_plan(
    spec: WorldSpec, plan: tuple[Action, ...] | list[Action], start: State | None = None
) -> tuple[State, int]:
    """Re-ejecuta un plan aplicando `Result(s, a)` con validación estricta.

    Devuelve el estado final y el costo acumulado. Si algún paso no es legal,
    `transition.result` lanza `IllegalActionError` indicando la precondición
    violada. Es el chequeo independiente del plan que produce la búsqueda.
    """

    state = start if start is not None else initial_state(spec)
    total = 0
    for action in plan:
        state = apply_action(spec, state, action)
        total += action.cost
    return state, total


def format_plan(spec: WorldSpec, result: SearchResult) -> str:
    """Representación legible del plan interno (no es el contrato visual)."""

    if not result.solution_found:
        return f"{result.status.value}: {result.message}"

    lines = [
        f"{result.status.value} — {len(result.plan)} acciones, costo total {result.total_cost}",
        f"  s0: {describe_state(spec, result.states[0])}",
    ]
    for i, action in enumerate(result.plan, start=1):
        lines.append(f"  {i:>3}. {action.describe():<46} | {describe_state(spec, result.states[i])}")
    lines.append(f"  meta alcanzada: {is_goal(spec, result.states[-1])}")
    return "\n".join(lines)
