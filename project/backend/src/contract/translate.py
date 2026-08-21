"""Traducción del plan interno al contrato visual.

    acción interna del agente  ──►  1..n operaciones visuales

Esta capa **no planifica ni reordena nada**: recorre el plan que ya produjo el
motor y reexpresa cada acción en el vocabulario cerrado de `CONTRATO.md`. Dos
invariantes lo garantizan y se verifican en tiempo de ejecución:

1. El costo de las operaciones visuales emitidas por una acción interna suma
   exactamente el costo de esa acción interna.
2. El costo total del plan visual es idéntico al `total_cost` del motor.

Hoy las siete acciones internas tienen traducción 1:1 (las cuatro operativas
viajan dentro de `INTERACT`), pero la firma devuelve una *secuencia* de pasos a
propósito: si mañana el modelo interno incorpora una macro-acción (por ejemplo
un `SWAP` que suelta y recoge en un mismo movimiento), se expande aquí sin tocar
el motor ni el endpoint.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from agent import Action, ActionKind, IN_INVENTORY, State, WorldSpec, is_goal

from .visual import InteractAction, VisualOp, VisualStep, validate_steps


class TranslationError(ValueError):
    """El plan interno no pudo reexpresarse en el contrato visual."""


#: Acción interna -> acción de INTERACT (CONTRATO.md §3.4).
_INTERACT_MAP = {
    ActionKind.OPEN_DOOR: InteractAction.OPEN_DOOR,
    ActionKind.REPAIR: InteractAction.REPAIR,
    ActionKind.ACTIVATE: InteractAction.ACTIVATE,
    ActionKind.RECHARGE: InteractAction.RECHARGE,
}


def translate_action(action: Action) -> tuple[VisualStep, ...]:
    """Traduce una acción interna a la secuencia de operaciones visuales."""

    kind = action.kind

    if kind is ActionKind.MOVE:
        steps: tuple[VisualStep, ...] = (
            VisualStep(
                op=VisualOp.MOVE,
                cost=action.cost,
                origin=action.origin,
                destination=action.target,
            ),
        )
    elif kind is ActionKind.PICKUP:
        steps = (VisualStep(op=VisualOp.PICKUP, cost=action.cost, item=action.item),)
    elif kind is ActionKind.DROP:
        steps = (VisualStep(op=VisualOp.DROP, cost=action.cost, item=action.item),)
    elif kind in _INTERACT_MAP:
        steps = (
            VisualStep(
                op=VisualOp.INTERACT,
                cost=action.cost,
                target=action.target,
                action=_INTERACT_MAP[kind],
                # Solo REPAIR declara material; el resto lo deja en None.
                consumes=action.consumes if kind is ActionKind.REPAIR else None,
            ),
        )
    else:
        raise TranslationError(f"acción interna sin traducción visual: {action.kind}")

    # Invariante 1: la traducción no puede inventar ni perder costo.
    emitted = sum(step.cost for step in steps)
    if emitted != action.cost:
        raise TranslationError(
            f"{action.describe()}: la traducción emite costo {emitted} "
            f"y la acción interna cuesta {action.cost}"
        )
    return steps


def translate_plan(
    spec: WorldSpec, plan: Sequence[Action], expected_cost: int | None = None
) -> list[VisualStep]:
    """Traduce el plan completo y lo audita contra el contrato."""

    steps: list[VisualStep] = []
    for action in plan:
        steps.extend(translate_action(action))

    validate_steps(spec, steps)

    # Invariante 2: el costo total del plan visual es el del motor.
    total = sum(step.cost for step in steps)
    if expected_cost is not None and total != expected_cost:
        raise TranslationError(
            f"el plan visual suma {total} y el motor calculó {expected_cost}"
        )
    return steps


# ---------------------------------------------------------------------------
# Traza de ejecución para la visualización
# ---------------------------------------------------------------------------


def _payload_of(spec: WorldSpec, state: State) -> list[str]:
    return [
        spec.items[i].name
        for i, value in enumerate(state.objects)
        if value == IN_INVENTORY
    ]


def state_snapshot(spec: WorldSpec, state: State, *, step: int, energy_spent: int) -> dict[str, Any]:
    """Estado del mundo en vocabulario visual (CLOSED/OPEN, DAMAGED/OK, ...)."""

    return {
        "step": step,
        "zone": state.pos,
        "battery": state.battery,
        "energy_spent": energy_spent,
        "payload": _payload_of(spec, state),
        "doors": {
            door.id: ("OPEN" if state.doors[i] == 1 else "CLOSED")
            for i, door in enumerate(spec.doors)
        },
        "panels": {
            panel.id: ("OK" if state.panels[i] == 1 else "DAMAGED")
            for i, panel in enumerate(spec.panels)
        },
        "stations": {
            station.id: ("ONLINE" if state.stations[i] == 1 else "OFFLINE")
            for i, station in enumerate(spec.stations)
        },
        "goal_reached": is_goal(spec, state),
    }


def build_trace(
    spec: WorldSpec, plan: Sequence[Action], states: Sequence[State]
) -> list[dict[str, Any]]:
    """Estado resultante tras cada paso visual, para que el frontend anime.

    `step` es el número de operaciones visuales ejecutadas: 0 es el estado
    inicial y el último coincide con `len(steps)`. Así el índice de la traza y
    el índice del plan visual siempre están alineados, incluso si una acción
    interna llegara a traducirse en varias operaciones.
    """

    if len(states) != len(plan) + 1:
        raise TranslationError(
            f"traza inconsistente: {len(states)} estados para {len(plan)} acciones"
        )

    trace = [state_snapshot(spec, states[0], step=0, energy_spent=0)]
    step_index = 0
    spent = 0
    for action, state in zip(plan, states[1:]):
        step_index += len(translate_action(action))
        spent += action.cost
        trace.append(state_snapshot(spec, state, step=step_index, energy_spent=spent))
    return trace


def steps_to_dicts(steps: Iterable[VisualStep]) -> list[dict[str, Any]]:
    return [step.to_dict() for step in steps]
