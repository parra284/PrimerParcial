"""Vocabulario cerrado del plan visual (CONTRATO.md §3).

Este módulo define **lo que el banco de pruebas acepta**, nada más:

    op     ∈ { MOVE, PICKUP, DROP, INTERACT }
    action ∈ { OPEN_DOOR, REPAIR, ACTIVATE, RECHARGE }   (solo dentro de INTERACT)

No sabe nada de búsqueda ni de estados: es la gramática de salida. El paquete
`agent` (modelo interno de IA) no importa este módulo — la dependencia va en un
solo sentido: `contract` → `agent`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from agent import WorldSpec


class ContractError(ValueError):
    """Un paso no cumple el contrato cerrado de CONTRATO.md."""


class VisualOp(str, Enum):
    """Las cuatro operaciones que entiende el frontend."""

    MOVE = "MOVE"
    PICKUP = "PICKUP"
    DROP = "DROP"
    INTERACT = "INTERACT"


class InteractAction(str, Enum):
    """Los cuatro valores admitidos en el campo `action` de un INTERACT."""

    OPEN_DOOR = "OPEN_DOOR"
    REPAIR = "REPAIR"
    ACTIVATE = "ACTIVATE"
    RECHARGE = "RECHARGE"


@dataclass(frozen=True, slots=True)
class VisualStep:
    """Un paso del plan tal como lo consume el frontend."""

    op: VisualOp
    cost: int
    origin: str | None = None    # MOVE: se serializa como "from"
    destination: str | None = None  # MOVE: se serializa como "to"
    item: str | None = None      # PICKUP / DROP
    target: str | None = None    # INTERACT
    action: InteractAction | None = None
    consumes: str | None = None  # INTERACT + REPAIR

    def to_dict(self) -> dict[str, Any]:
        """Serializa emitiendo únicamente los campos que el contrato define."""

        if self.op is VisualOp.MOVE:
            return {
                "op": self.op.value,
                "from": self.origin,
                "to": self.destination,
                "cost": self.cost,
            }
        if self.op in (VisualOp.PICKUP, VisualOp.DROP):
            return {"op": self.op.value, "item": self.item, "cost": self.cost}

        step: dict[str, Any] = {
            "op": self.op.value,
            "target": self.target,
            "action": self.action.value if self.action else None,
            "cost": self.cost,
        }
        if self.action is InteractAction.REPAIR and self.consumes is not None:
            step["consumes"] = self.consumes
        return step

    def describe(self) -> str:
        if self.op is VisualOp.MOVE:
            return f"MOVE {self.origin}->{self.destination} (cost {self.cost})"
        if self.op in (VisualOp.PICKUP, VisualOp.DROP):
            return f"{self.op.value} {self.item} (cost {self.cost})"
        extra = f" consumes={self.consumes}" if self.consumes else ""
        return f"INTERACT {self.action.value if self.action else '?'} {self.target}{extra} (cost {self.cost})"


# ---------------------------------------------------------------------------
# Auditoría del plan emitido
# ---------------------------------------------------------------------------


def validate_steps(spec: WorldSpec, steps: list[VisualStep]) -> None:
    """Comprueba vocabulario y **costos oficiales** (CONTRATO.md §3 y §5).

    Los costos no se inventan: provienen del escenario. Como el motor ya usa
    esos mismos costos, esta función es una red de seguridad que detecta
    cualquier deriva entre el plan interno y el plan emitido.
    """

    for index, step in enumerate(steps, start=1):
        where = f"paso {index} ({step.describe()})"

        if not isinstance(step.op, VisualOp):
            raise ContractError(f"{where}: op fuera del contrato")
        if step.cost <= 0:
            raise ContractError(f"{where}: costo inválido {step.cost}")

        if step.op is VisualOp.MOVE:
            if step.origin is None or step.destination is None:
                raise ContractError(f"{where}: MOVE exige from y to")
            corridors = [
                c
                for c in spec.adjacency.get(step.origin, ())
                if c.to == step.destination
            ]
            if not corridors:
                raise ContractError(
                    f"{where}: no existe corredor {step.origin}->{step.destination}"
                )
            if step.cost not in {c.cost for c in corridors}:
                raise ContractError(
                    f"{where}: el costo no coincide con ningún corredor "
                    f"{step.origin}->{step.destination} ({sorted({c.cost for c in corridors})})"
                )
            continue

        if step.op in (VisualOp.PICKUP, VisualOp.DROP):
            if step.item is None:
                raise ContractError(f"{where}: falta el campo item")
            if step.item not in spec.slots_by_name:
                raise ContractError(f"{where}: objeto desconocido {step.item}")
            official = spec.cost_pickup if step.op is VisualOp.PICKUP else spec.cost_drop
            if step.cost != official:
                raise ContractError(f"{where}: costo {step.cost}, oficial {official}")
            continue

        # --- INTERACT -------------------------------------------------
        if not isinstance(step.action, InteractAction):
            raise ContractError(f"{where}: action fuera del contrato ({step.action!r})")
        if step.target is None:
            raise ContractError(f"{where}: INTERACT exige target")

        if step.action is InteractAction.OPEN_DOOR:
            if step.target not in spec.door_index:
                raise ContractError(f"{where}: puerta desconocida {step.target}")
        elif step.action is InteractAction.REPAIR:
            if step.target not in spec.panel_index:
                raise ContractError(f"{where}: panel desconocido {step.target}")
            required = spec.panels[spec.panel_index[step.target]].material
            if required is not None and step.consumes != required:
                raise ContractError(
                    f"{where}: consumes={step.consumes!r} pero el panel exige {required!r}"
                )
        elif step.action is InteractAction.ACTIVATE:
            if step.target not in spec.station_index:
                raise ContractError(f"{where}: estación desconocida {step.target}")
        elif step.action is InteractAction.RECHARGE:
            if step.target not in set(spec.chargers.values()):
                raise ContractError(f"{where}: cargador desconocido {step.target}")

        official = (
            spec.cost_recharge
            if step.action is InteractAction.RECHARGE
            else spec.cost_interact
        )
        if step.cost != official:
            raise ContractError(f"{where}: costo {step.cost}, oficial {official}")
