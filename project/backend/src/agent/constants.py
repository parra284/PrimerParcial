"""Constantes y enumeraciones del modelo interno del agente.

Referencia: `project/design.md` — secciones «Estado» y «Tabla de Acciones».

Este módulo (y todo el paquete `agent`) es *modelo interno de IA*: no conoce
HTTP, ni el frontend, ni el contrato visual (`MOVE | PICKUP | DROP | INTERACT`).
La traducción a operaciones visuales vive fuera de este paquete.
"""

from __future__ import annotations

from enum import Enum

# ---------------------------------------------------------------------------
# Valores no espaciales admitidos en la tupla O (design.md §Estado)
#
#   O_i ∈ {Z_1, ..., Z_n, EN_INVENTARIO, USADO, OLVIDADO}
#
# EN_INVENTARIO : el objeto ocupa capacidad de carga del robot.
# USADO         : material consumible gastado en un REPAIR (design.md §Relevancia 2).
# OLVIDADO      : posición muerta. El objeto quedó en el suelo y ya no puede
#                 volver a intervenir en ningún plan (todas las puertas/paneles
#                 que servía están resueltos), así que su zona concreta deja de
#                 ser información relevante y se colapsa a esta constante.
# ---------------------------------------------------------------------------
IN_INVENTORY = "@EN_INVENTARIO"
USED = "@USADO"
FORGOTTEN = "@OLVIDADO"

#: Valores de O que no son una zona del mapa.
NON_SPATIAL = frozenset({IN_INVENTORY, USED, FORGOTTEN})

#: Valores de O terminales: el objeto ya no vuelve a ser recogible nunca.
DEAD = frozenset({USED, FORGOTTEN})


class ItemKind(str, Enum):
    """Clasificación fija de cada objeto (design.md §Información fija)."""

    KEY = "KEY"            # abre puertas, no se consume
    TOOL = "TOOL"          # herramienta reutilizable, no se consume
    MATERIAL = "MATERIAL"  # consumible: al reparar pasa a USADO


class ActionKind(str, Enum):
    """Acciones internas del agente (design.md §Tabla de Acciones)."""

    MOVE = "MOVE"
    PICKUP = "PICKUP"
    DROP = "DROP"
    OPEN_DOOR = "OPEN_DOOR"
    REPAIR = "REPAIR"
    ACTIVATE = "ACTIVATE"
    RECHARGE = "RECHARGE"


# --- Valores por defecto si el escenario no los declara --------------------
DEFAULT_BATTERY_MAX = 100
DEFAULT_CARGO_CAPACITY = 3
DEFAULT_ACTION_COSTS = {
    "pickup": 1,
    "drop": 1,
    "interact": 2,
    "recharge": 3,
}
