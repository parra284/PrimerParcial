"""Uniform Cost Search con Graph Search y dominancia de batería.

Referencia: `project/design.md` — §Estrategia de búsqueda, §Control de
Reexploración con Graph Search y §Batería como recurso y Regla de Dominancia.

Compromisos del diseño que este módulo respeta al pie de la letra:

1. `OPEN` es una cola de prioridad ordenada por g(n) (consumo de batería).
2. **La prueba de meta se hace al EXTRAER de `OPEN`, no al generar.** Probar al
   generar rompería la optimalidad.
3. `CLOSED` no guarda estados completos: mapea la configuración física
   ⟨pos, P, R, E, O⟩ → mayor batería vista. Un nodo con la misma configuración y
   batería menor o igual está dominado y se descarta sin expandir.
4. Si `OPEN` se vacía sin alcanzar la meta, la búsqueda termina y devuelve
   FAILURE. El espacio de estados es finito y todo costo es ≥ 1, así que la
   terminación está garantizada.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from heapq import heappop, heappush

from .actions import Action
from .state import PhysicalKey, State, initial_state, is_goal
from .transition import successors
from .world import WorldSpec


class SearchStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"          # OPEN se vació: la misión es imposible
    LIMIT_REACHED = "LIMIT_REACHED"  # se agotó un límite opcional de recursos


@dataclass(frozen=True, slots=True)
class SearchStats:
    expanded: int = 0
    generated: int = 0
    dominated_on_pop: int = 0
    dominated_on_generation: int = 0
    max_open_size: int = 0
    closed_size: int = 0
    elapsed_seconds: float = 0.0

    def describe(self) -> str:
        return (
            f"expandidos={self.expanded} generados={self.generated} "
            f"podados(pop)={self.dominated_on_pop} "
            f"podados(gen)={self.dominated_on_generation} "
            f"|OPEN|max={self.max_open_size} |CLOSED|={self.closed_size} "
            f"tiempo={self.elapsed_seconds:.2f}s"
        )


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Resultado explícito de la búsqueda: nunca una excepción, nunca un cuelgue."""

    status: SearchStatus
    plan: tuple[Action, ...] = ()
    total_cost: int | None = None
    states: tuple[State, ...] = ()  # s₀ … s_meta (len == len(plan) + 1)
    stats: SearchStats = field(default_factory=SearchStats)
    message: str = ""

    @property
    def solution_found(self) -> bool:
        return self.status is SearchStatus.SUCCESS


class _Node:
    """Nodo del grafo de búsqueda: estado + historial (g, padre, acción)."""

    __slots__ = ("state", "g", "parent", "action", "key")

    def __init__(
        self,
        state: State,
        g: int,
        parent: "_Node | None",
        action: Action | None,
        key: PhysicalKey | None = None,
    ):
        self.state = state
        self.g = g
        self.parent = parent
        self.action = action
        self.key = state.physical_key() if key is None else key


def _reconstruct(node: _Node) -> tuple[tuple[Action, ...], tuple[State, ...]]:
    plan: list[Action] = []
    states: list[State] = []
    current: _Node | None = node
    while current is not None:
        states.append(current.state)
        if current.action is not None:
            plan.append(current.action)
        current = current.parent
    plan.reverse()
    states.reverse()
    return tuple(plan), tuple(states)


def uniform_cost_search(
    spec: WorldSpec,
    *,
    start: State | None = None,
    node_limit: int | None = None,
    time_limit: float | None = None,
) -> SearchResult:
    """UCS (Dijkstra) en su variante Graph Search.

    `node_limit` y `time_limit` son cinturones de seguridad opcionales: con el
    valor por defecto `None` el algoritmo es exacto y termina por sí solo
    (`OPEN` vacío ⟹ FAILURE).
    """

    started = time.perf_counter()
    root = _Node(start if start is not None else initial_state(spec), 0, None, None)

    # OPEN se ordena por g(n); a igualdad de g se extrae primero el nodo con más
    # batería (`-b`), lo que llena CLOSED con el mejor valor cuanto antes y hace
    # que los empates queden dominados sin expandirse. El contador desempata al
    # final y evita comparar nodos entre sí.
    counter = 0
    open_heap: list[tuple[int, int, int, _Node]] = [(0, -root.state.battery, counter, root)]
    closed: dict[PhysicalKey, int] = {}
    # Frente de Pareto, por configuración física, de los pares (g, b) ya
    # generados: pares mutuamente no dominados. Es el mismo Principio de
    # Dominancia de design.md («n1 domina a n2 ⟺ b1 ≥ b2 y g1 ≤ g2») aplicado
    # también en la generación, para no meter en OPEN nodos que ya nacen
    # dominados. CLOSED sigue siendo el filtro autoritativo al extraer.
    pareto_front: dict[PhysicalKey, list[tuple[int, int]]] = {root.key: [(0, root.state.battery)]}

    expanded = generated = dominated_pop = dominated_gen = 0
    max_open = 1

    while open_heap:
        g, _, _, node = heappop(open_heap)
        state = node.state
        key = node.key

        # --- Filtro de dominancia al extraer (design.md §CLOSED) ---------
        best_battery = closed.get(key)
        if best_battery is not None and state.battery <= best_battery:
            dominated_pop += 1
            continue
        closed[key] = state.battery

        # --- Prueba de meta AL EXTRAER, nunca al generar -----------------
        if is_goal(spec, state):
            plan, states = _reconstruct(node)
            return SearchResult(
                status=SearchStatus.SUCCESS,
                plan=plan,
                total_cost=g,
                states=states,
                stats=SearchStats(
                    expanded=expanded,
                    generated=generated,
                    dominated_on_pop=dominated_pop,
                    dominated_on_generation=dominated_gen,
                    max_open_size=max_open,
                    closed_size=len(closed),
                    elapsed_seconds=time.perf_counter() - started,
                ),
                message=f"Plan óptimo de {len(plan)} acciones y costo {g}.",
            )

        expanded += 1

        if node_limit is not None and expanded >= node_limit:
            return _exhausted(
                f"Límite de {node_limit} nodos expandidos alcanzado sin agotar OPEN.",
                expanded, generated, dominated_pop, dominated_gen, max_open, closed, started,
            )
        if time_limit is not None and (time.perf_counter() - started) > time_limit:
            return _exhausted(
                f"Límite de {time_limit:.1f}s alcanzado sin agotar OPEN.",
                expanded, generated, dominated_pop, dominated_gen, max_open, closed, started,
            )

        for action, child_state in successors(spec, state):
            generated += 1
            child_key = child_state.physical_key()
            child_battery = child_state.battery
            child_g = g + action.cost

            # Mismo criterio de dominancia, aplicado al generar: un nodo que ya
            # sería descartado al extraerse no necesita ocupar memoria en OPEN.
            seen_battery = closed.get(child_key)
            if seen_battery is not None and child_battery <= seen_battery:
                dominated_gen += 1
                continue

            # ¿Se generó ya un nodo con la misma configuración física, costo
            # menor o igual y al menos tanta batería? Entonces este nace dominado.
            pareto = pareto_front.get(child_key)
            if pareto is None:
                pareto_front[child_key] = [(child_g, child_battery)]
            else:
                dominated = False
                dominates = False
                for gi, bi in pareto:
                    if gi <= child_g and bi >= child_battery:
                        dominated = True
                        break
                    if child_g <= gi and child_battery >= bi:
                        dominates = True
                if dominated:
                    dominated_gen += 1
                    continue
                if dominates:
                    pareto[:] = [
                        pair
                        for pair in pareto
                        if not (child_g <= pair[0] and child_battery >= pair[1])
                    ]
                pareto.append((child_g, child_battery))

            counter += 1
            heappush(
                open_heap,
                (child_g, -child_battery, counter, _Node(child_state, child_g, node, action, child_key)),
            )

        if len(open_heap) > max_open:
            max_open = len(open_heap)

    # OPEN vacío: no existe ningún plan que satisfaga la meta.
    return SearchResult(
        status=SearchStatus.FAILURE,
        plan=(),
        total_cost=None,
        states=(),
        stats=SearchStats(
            expanded=expanded,
            generated=generated,
            dominated_on_pop=dominated_pop,
            dominated_on_generation=dominated_gen,
            max_open_size=max_open,
            closed_size=len(closed),
            elapsed_seconds=time.perf_counter() - started,
        ),
        message="FAILURE: OPEN se vació sin alcanzar la meta; la misión es imposible.",
    )


def _exhausted(
    message: str,
    expanded: int,
    generated: int,
    dominated_pop: int,
    dominated_gen: int,
    max_open: int,
    closed: dict[PhysicalKey, int],
    started: float,
) -> SearchResult:
    return SearchResult(
        status=SearchStatus.LIMIT_REACHED,
        plan=(),
        total_cost=None,
        states=(),
        stats=SearchStats(
            expanded=expanded,
            generated=generated,
            dominated_on_pop=dominated_pop,
            dominated_on_generation=dominated_gen,
            max_open_size=max_open,
            closed_size=len(closed),
            elapsed_seconds=time.perf_counter() - started,
        ),
        message=message,
    )
