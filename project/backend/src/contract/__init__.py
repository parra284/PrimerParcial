"""Capa de traducción: modelo interno de IA → contrato visual del frontend.

Separación exigida por el enunciado (§5) y por `CONTRATO.md`:

    agent/     modelo interno de IA   (estados, acciones internas, UCS)
    contract/  representación visual  (MOVE | PICKUP | DROP | INTERACT)

La dependencia va en un solo sentido: `contract` importa `agent`; `agent` no
sabe que este paquete existe. La capa visual no decide nada de la lógica del
agente: solo reexpresa el plan ya calculado, sin alterar su orden ni su costo.
"""

from __future__ import annotations

from .response import build_solve_response
from .translate import (
    TranslationError,
    build_trace,
    state_snapshot,
    steps_to_dicts,
    translate_action,
    translate_plan,
)
from .visual import (
    ContractError,
    InteractAction,
    VisualOp,
    VisualStep,
    validate_steps,
)

__all__ = [
    "ContractError",
    "InteractAction",
    "TranslationError",
    "VisualOp",
    "VisualStep",
    "build_solve_response",
    "build_trace",
    "state_snapshot",
    "steps_to_dicts",
    "translate_action",
    "translate_plan",
    "validate_steps",
]
