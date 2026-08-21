"""Acciones internas del agente.

Referencia: `project/design.md` — §Tabla de Acciones.

Estas son las acciones del **modelo de IA**, no las operaciones visuales del
contrato. `OPEN_DOOR`, `REPAIR`, `ACTIVATE` y `RECHARGE` son acciones internas
de pleno derecho; su traducción a `INTERACT` es responsabilidad de otra capa.
"""

from __future__ import annotations

from typing import NamedTuple

from .constants import ActionKind


class Action(NamedTuple):
    """Una acción interna aplicable, con su costo en unidades de batería."""

    kind: ActionKind
    cost: int
    target: str | None = None    # zona destino | puerta | panel | estación | cargador
    item: str | None = None      # PICKUP/DROP: objeto; OPEN_DOOR: llave usada
    tool: str | None = None      # REPAIR: herramienta usada (no se consume)
    consumes: str | None = None  # REPAIR: tipo de material consumido
    origin: str | None = None    # MOVE: zona de origen
    slot: int | None = None      # índice en O del objeto afectado (uso interno)

    def describe(self) -> str:
        if self.kind is ActionKind.MOVE:
            body = f"{self.origin} -> {self.target}"
        elif self.kind is ActionKind.OPEN_DOOR:
            body = f"{self.target} [{self.item}]" if self.item else f"{self.target}"
        elif self.kind is ActionKind.REPAIR:
            parts = [p for p in (self.tool, self.consumes) if p]
            body = f"{self.target} [{' + '.join(parts)}]" if parts else f"{self.target}"
        elif self.kind in (ActionKind.PICKUP, ActionKind.DROP):
            body = f"{self.item}"
        else:
            body = f"{self.target}"
        return f"{self.kind.value} {body} (costo {self.cost})"


def move(origin: str, destination: str, cost: int) -> Action:
    return Action(ActionKind.MOVE, cost, target=destination, origin=origin)


def pickup(item: str, cost: int, slot: int) -> Action:
    return Action(ActionKind.PICKUP, cost, item=item, slot=slot)


def drop(item: str, cost: int, slot: int, zone: str) -> Action:
    return Action(ActionKind.DROP, cost, item=item, slot=slot, target=zone)


def open_door(door: str, key: str | None, cost: int) -> Action:
    return Action(ActionKind.OPEN_DOOR, cost, target=door, item=key)


def repair(
    panel: str, tool: str | None, material: str | None, cost: int, slot: int | None
) -> Action:
    return Action(
        ActionKind.REPAIR, cost, target=panel, tool=tool, consumes=material, slot=slot
    )


def activate(station: str, cost: int) -> Action:
    return Action(ActionKind.ACTIVATE, cost, target=station)


def recharge(charger: str, cost: int) -> Action:
    return Action(ActionKind.RECHARGE, cost, target=charger)
