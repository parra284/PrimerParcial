"""Utilidades compartidas por las pruebas del Entregable 3.

Las pruebas se ejecutan **contra el motor de la Fase 1** (`agent/`), no contra
el endpoint HTTP: lo que se valida son propiedades del modelo de búsqueda.

Cada escenario vive en `project/scenarios/` como archivo JSON aparte; aquí no
se construyen instancias a mano.
"""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
SRC = BACKEND / "src"
SCENARIOS = BACKEND.parent / "scenarios"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agent import Action, WorldSpec, parse_scenario, solve  # noqa: E402
from agent import actions as act  # noqa: E402


def load(name: str = "scenario.json") -> dict[str, Any]:
    """Carga un escenario de `project/scenarios/`."""
    path = SCENARIOS / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def spec_of(name: str = "scenario.json") -> WorldSpec:
    return parse_scenario(load(name))


@lru_cache(maxsize=4)
def solved(name: str = "scenario.json"):
    """Resuelve un escenario una sola vez por proceso (la demo tarda ~15 s)."""
    spec = parse_scenario(load(name))
    return spec, solve(spec)


# --- constructores de acciones sin costos ni slots escritos a mano ---------


def corridor_cost(spec: WorldSpec, origin: str, destination: str) -> int:
    for corridor in spec.adjacency[origin]:
        if corridor.to == destination:
            return corridor.cost
    raise AssertionError(f"no existe corredor {origin}->{destination}")


def slot_of(spec: WorldSpec, name: str) -> int:
    return spec.slots_by_name[name][0]


def move(spec: WorldSpec, origin: str, destination: str) -> Action:
    return act.move(origin, destination, corridor_cost(spec, origin, destination))


def pickup(spec: WorldSpec, item: str) -> Action:
    return act.pickup(item, spec.cost_pickup, slot_of(spec, item))


def drop(spec: WorldSpec, item: str, zone: str) -> Action:
    return act.drop(item, spec.cost_drop, slot_of(spec, item), zone)


def open_door(spec: WorldSpec, door: str) -> Action:
    return act.open_door(door, spec.doors[spec.door_index[door]].key, spec.cost_interact)


def repair(spec: WorldSpec, panel_id: str) -> Action:
    panel = spec.panels[spec.panel_index[panel_id]]
    return act.repair(
        panel.id,
        panel.tool,
        panel.material,
        spec.cost_interact,
        slot_of(spec, panel.material) if panel.material else None,
    )


def activate(spec: WorldSpec, station: str) -> Action:
    return act.activate(station, spec.cost_interact)


def recharge(spec: WorldSpec, zone: str) -> Action:
    return act.recharge(spec.chargers[zone], spec.cost_recharge)


# --- salida legible --------------------------------------------------------


def title(text: str) -> None:
    print("\n" + "=" * 74)
    print(text)
    print("=" * 74)


def ok(text: str) -> None:
    print(f"  [OK] {text}")


def info(text: str) -> None:
    print(f"       {text}")


def plan_moves(plan: tuple[Action, ...]) -> str:
    moves = [a for a in plan if a.kind.value == "MOVE"]
    if not moves:
        return "(sin desplazamientos)"
    return " -> ".join([moves[0].origin or "?"] + [a.target or "?" for a in moves])


def describe_plan(spec: WorldSpec, plan: tuple[Action, ...]) -> str:
    return " | ".join(a.describe() for a in plan)
