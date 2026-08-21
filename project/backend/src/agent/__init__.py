"""Modelo interno de IA del agente (Emergency Control).

Paquete autocontenido: implementa el diseño de `project/design.md` — estado
⟨pos, b, P, R, E, O⟩, acciones internas, modelo de transición, podas, prueba de
meta, función de costo y Uniform Cost Search con Graph Search.

No importa FastAPI, no conoce el frontend y no emite las operaciones visuales
del contrato (`MOVE | PICKUP | DROP | INTERACT`). La traducción del plan interno
al contrato visual es una capa aparte.

Uso típico::

    from agent import solve_scenario

    result = solve_scenario(scenario_dict)
    if result.solution_found:
        for action in result.plan:
            print(action.describe())
        print(result.total_cost)
"""

from __future__ import annotations

from .actions import Action
from .constants import (
    DEAD,
    FORGOTTEN,
    IN_INVENTORY,
    NON_SPATIAL,
    USED,
    ActionKind,
    ItemKind,
)
from .search import (
    SearchResult,
    SearchStats,
    SearchStatus,
    uniform_cost_search,
)
from .solver import format_plan, replay_plan, solve, solve_scenario
from .state import (
    State,
    build_state,
    canonical_objects,
    carried_units,
    carried_weight,
    describe_state,
    free_capacity,
    initial_state,
    inventory_slots,
    is_goal,
    useful_units,
)
from .transition import (
    IllegalActionError,
    applicable_actions,
    result,
    successors,
)
from .world import (
    Corridor,
    DoorSpec,
    ItemSpec,
    PanelSpec,
    ScenarioError,
    StationSpec,
    WorldSpec,
    parse_scenario,
)

__all__ = [
    "Action",
    "ActionKind",
    "Corridor",
    "DEAD",
    "DoorSpec",
    "FORGOTTEN",
    "IN_INVENTORY",
    "IllegalActionError",
    "ItemKind",
    "ItemSpec",
    "NON_SPATIAL",
    "PanelSpec",
    "ScenarioError",
    "SearchResult",
    "SearchStats",
    "SearchStatus",
    "State",
    "StationSpec",
    "USED",
    "WorldSpec",
    "applicable_actions",
    "build_state",
    "canonical_objects",
    "carried_units",
    "carried_weight",
    "describe_state",
    "format_plan",
    "free_capacity",
    "initial_state",
    "inventory_slots",
    "is_goal",
    "parse_scenario",
    "replay_plan",
    "result",
    "solve",
    "solve_scenario",
    "successors",
    "uniform_cost_search",
    "useful_units",
]
