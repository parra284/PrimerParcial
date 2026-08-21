"""Applicable(s), Result(s, a) y la generación de sucesores.

Referencia: `project/design.md` — §Tabla de Acciones, §Reglas de Poda en la
Generación de Sucesores y §Modelo de transición.

Separación deliberada de responsabilidades:

* `result(spec, s, a)` implementa **Result(s, a)**: exige únicamente las
  precondiciones lógicas de la tabla de acciones más la condición global
  `b ≥ Costo(a)` (las leyes físicas del mundo). Es una función parcial: si la
  acción no es legal, lanza `IllegalActionError`.
* `applicable_actions(spec, s)` implementa **Applicable(s)**: legalidad física
  **+ las reglas de poda**, que descartan acciones legales pero que ningún plan
  óptimo necesita.

`legal según el simulador ≠ relevante para buscar`: la diferencia entre ambas
funciones es exactamente esa frase.

Podas aplicadas en `applicable_actions` (todas conservan el óptimo):

1. **PICKUP obsoleto** — design.md §Podas, regla 1. No se recoge un objeto cuyas
   puertas/paneles asociados ya están resueltos.
   *Extensión (misma regla, aplicada por unidades):* tampoco se recoge la unidad
   *sobrante* de un material cuando el robot ya carga tantas unidades como
   paneles pendientes la exigen: esa unidad no podrá consumirse nunca.
2. **DROP por ineficiencia** — design.md §Podas, regla 2. Solo se suelta cuando
   un objeto relevante de esta zona no cabe en el inventario.
   *Extensión (misma regla):* si el inventario ya carga lastre (un objeto que no
   volverá a servir), soltar en su lugar un objeto todavía útil está dominado —
   libera el mismo peso y además obliga a volver por él.
3. **Recarga ineficiente** — design.md §Podas, regla 3. No se recarga cuando la
   ganancia de batería no supera el costo de la recarga.
4. *Extensión de la regla 1 a las estaciones:* no se activa una estación que no
   es meta ni prerrequisito (directo o transitivo) de una meta.

Las tres extensiones son casos particulares del mismo criterio de relevancia de
design.md §«Relevancia: objetos que ya no cambian a futuro»; conviene dejarlas
escritas también en design.md para que diseño e implementación coincidan.
"""

from __future__ import annotations

from typing import Iterator

from . import actions as act
from .actions import Action
from .constants import IN_INVENTORY, USED, ActionKind
from .state import (
    State,
    build_state,
    carried_units,
    free_capacity,
    relevance_vector,
)
from .world import ItemSpec, WorldSpec


class IllegalActionError(ValueError):
    """La acción no pertenece a Applicable(s): Result(s, a) no está definida."""


# ---------------------------------------------------------------------------
# Consultas auxiliares
# ---------------------------------------------------------------------------


def _relevant_items_here(spec: WorldSpec, state: State) -> list[ItemSpec]:
    """Objetos del suelo de la zona actual que todavía vale la pena recoger.

    Aplica la **poda de recogida obsoleta** (design.md §Podas, regla 1):

    * se descarta el objeto cuyas puertas/paneles asociados ya están resueltos
      (`useful_units == 0`);
    * se descarta la unidad *sobrante* de un material: si quedan 2 paneles
      pendientes que piden `FUSE` y el robot ya lleva 2 fusibles, un tercero no
      puede consumirse nunca — es tan obsoleto como el caso anterior;
    * de dos unidades intercambiables presentes en la misma zona solo se ofrece
      una (misma clase de equivalencia ⟹ mismo sucesor canónico).
    """

    objects = state.objects
    pos = state.pos
    relevance = relevance_vector(spec, state.doors, state.panels)
    seen: set[str] = set()
    found: list[ItemSpec] = []
    for item in spec.items:
        if objects[item.index] != pos:
            continue
        if item.eq_class in seen:
            continue
        units = relevance[item.index]
        if units <= 0:
            continue
        if carried_units(spec, state, item.eq_class) >= units:
            continue
        seen.add(item.eq_class)
        found.append(item)
    return found


def _find_slot(spec: WorldSpec, state: State, name: str, where: str) -> int | None:
    objects = state.objects
    for index in spec.slots_by_name.get(name, ()):
        if objects[index] == where:
            return index
    return None


def _corridor_for(spec: WorldSpec, state: State, destination: str, cost: int | None):
    for corridor in spec.adjacency.get(state.pos, ()):
        if corridor.to != destination:
            continue
        if cost is not None and corridor.cost != cost:
            continue
        return corridor
    return None


# ---------------------------------------------------------------------------
# Applicable(s)
# ---------------------------------------------------------------------------


def applicable_actions(spec: WorldSpec, state: State) -> list[Action]:
    """Acciones internas aplicables en `state`, ya podadas."""

    battery = state.battery
    pos = state.pos
    doors_state = state.doors
    panels_state = state.panels
    stations_state = state.stations
    objects = state.objects
    out: list[Action] = []

    # --- MOVE(Z) --------------------------------------------------------
    for corridor in spec.adjacency.get(pos, ()):
        if corridor.door is not None and doors_state[corridor.door] == 0:
            continue
        if battery < corridor.cost:
            continue
        out.append(act.move(pos, corridor.to, corridor.cost))

    relevant_here = _relevant_items_here(spec, state)
    free = free_capacity(spec, state)

    # --- PICKUP(Obj) ----------------------------------------------------
    if battery >= spec.cost_pickup:
        for item in relevant_here:
            if item.weight <= free:
                out.append(act.pickup(item.name, spec.cost_pickup, item.index))

    # --- DROP(Obj) ------------------------------------------------------
    # Poda de DROP por ineficiencia (design.md §Podas, regla 2): solo se suelta
    # cuando no cabe un objeto relevante presente en esta zona. Soltar en otro
    # sitio nunca ayuda: el costo de movimiento no depende de la carga, así que
    # posponer el DROP hasta la zona donde hace falta el hueco jamás es peor.
    blocked = any(item.weight > free for item in relevant_here)
    if battery >= spec.cost_drop and blocked:
        relevance = relevance_vector(spec, doors_state, panels_state)
        # Si el inventario ya carga lastre (un objeto que no volverá a servir
        # jamás), soltar en su lugar un objeto todavía útil está dominado:
        # libera el mismo peso y obliga a volver por él. Solo se restringe
        # frente a lastre de peso suficiente.
        ballast = max(
            (
                spec.items[i].weight
                for i, value in enumerate(objects)
                if value == IN_INVENTORY and relevance[i] == 0
            ),
            default=0,
        )
        seen: set[str] = set()
        for item in spec.items:
            if objects[item.index] != IN_INVENTORY:
                continue
            if relevance[item.index] > 0 and ballast >= item.weight:
                continue
            if item.eq_class in seen:
                continue
            seen.add(item.eq_class)
            out.append(act.drop(item.name, spec.cost_drop, item.index, pos))

    if battery >= spec.cost_interact:
        interact = spec.cost_interact

        # --- OPEN_DOOR(P_i, Llave) --------------------------------------
        for index in spec.doors_by_zone[pos]:
            if doors_state[index] == 1:
                continue
            door = spec.doors[index]
            if door.key is not None and _find_slot(spec, state, door.key, IN_INVENTORY) is None:
                continue
            out.append(act.open_door(door.id, door.key, interact))

        # --- REPAIR(R_i, Obj) -------------------------------------------
        for index in spec.panels_by_zone[pos]:
            if panels_state[index] == 1:
                continue
            panel = spec.panels[index]
            if panel.tool is not None and _find_slot(spec, state, panel.tool, IN_INVENTORY) is None:
                continue
            material_slot: int | None = None
            if panel.material is not None:
                material_slot = _find_slot(spec, state, panel.material, IN_INVENTORY)
                if material_slot is None:
                    continue
            out.append(act.repair(panel.id, panel.tool, panel.material, interact, material_slot))

        # --- ACTIVATE(E_j) ----------------------------------------------
        for index in spec.stations_by_zone[pos]:
            if stations_state[index] == 1:
                continue
            station = spec.stations[index]
            # Poda de relevancia: activar una estación que no es meta ni
            # prerrequisito (directo o transitivo) de una meta no habilita
            # nada — es la misma regla 1 aplicada a E.
            if index not in spec.useful_stations:
                continue
            if any(panels_state[p] == 0 for p in station.required_panels):
                continue
            if any(stations_state[s] == 0 for s in station.required_stations):
                continue
            out.append(act.activate(station.id, interact))

    # --- RECHARGE() -----------------------------------------------------
    charger = spec.chargers.get(pos)
    if charger is not None and battery >= spec.cost_recharge:
        # Poda de recarga ineficiente (design.md §Podas, regla 3): recargar
        # devuelve `battery_max - b` unidades a cambio de `cost_recharge`. Si la
        # ganancia no supera al costo la acción nunca mejora un plan óptimo.
        if battery + spec.cost_recharge < spec.battery_max:
            out.append(act.recharge(charger, spec.cost_recharge))

    return out


# ---------------------------------------------------------------------------
# Result(s, a)
# ---------------------------------------------------------------------------


def result(spec: WorldSpec, state: State, action: Action) -> State:
    """Result(s, a) con validación estricta de las precondiciones."""

    _validate(spec, state, action)
    return _apply(spec, state, action)


def _validate(spec: WorldSpec, state: State, action: Action) -> None:
    if action.cost <= 0:
        raise IllegalActionError(f"{action.describe()}: el costo debe ser > 0")
    # Condición global de ejecución: b ≥ Costo(a).
    if state.battery < action.cost:
        raise IllegalActionError(
            f"{action.describe()}: batería insuficiente ({state.battery} < {action.cost})"
        )

    kind = action.kind

    if kind is ActionKind.MOVE:
        corridor = _corridor_for(spec, state, action.target or "", action.cost)
        if corridor is None:
            raise IllegalActionError(
                f"MOVE {state.pos} -> {action.target}: no existe corredor con costo {action.cost}"
            )
        if corridor.door is not None and state.doors[corridor.door] == 0:
            raise IllegalActionError(
                f"MOVE {state.pos} -> {action.target}: puerta {spec.doors[corridor.door].id} cerrada"
            )
        return

    if kind is ActionKind.PICKUP:
        slot = _slot_of(spec, state, action, expected=state.pos)
        item = spec.items[slot]
        if item.weight > free_capacity(spec, state):
            raise IllegalActionError(f"PICKUP {item.name}: inventario lleno")
        return

    if kind is ActionKind.DROP:
        _slot_of(spec, state, action, expected=IN_INVENTORY)
        return

    if kind is ActionKind.OPEN_DOOR:
        index = spec.door_index.get(action.target or "")
        if index is None:
            raise IllegalActionError(f"OPEN_DOOR: puerta desconocida {action.target}")
        door = spec.doors[index]
        if state.doors[index] == 1:
            raise IllegalActionError(f"OPEN_DOOR {door.id}: ya está abierta")
        if state.pos not in door.zones:
            raise IllegalActionError(f"OPEN_DOOR {door.id}: el robot no está en {door.zones}")
        if door.key is not None and _find_slot(spec, state, door.key, IN_INVENTORY) is None:
            raise IllegalActionError(f"OPEN_DOOR {door.id}: falta la llave {door.key}")
        return

    if kind is ActionKind.REPAIR:
        index = spec.panel_index.get(action.target or "")
        if index is None:
            raise IllegalActionError(f"REPAIR: panel desconocido {action.target}")
        panel = spec.panels[index]
        if state.panels[index] == 1:
            raise IllegalActionError(f"REPAIR {panel.id}: ya está reparado")
        if panel.zone != state.pos:
            raise IllegalActionError(f"REPAIR {panel.id}: el robot no está en {panel.zone}")
        if panel.tool is not None and _find_slot(spec, state, panel.tool, IN_INVENTORY) is None:
            raise IllegalActionError(f"REPAIR {panel.id}: falta la herramienta {panel.tool}")
        if panel.material is not None:
            if action.consumes is not None and action.consumes != panel.material:
                raise IllegalActionError(
                    f"REPAIR {panel.id}: consume {action.consumes} pero exige {panel.material}"
                )
            if _find_slot(spec, state, panel.material, IN_INVENTORY) is None:
                raise IllegalActionError(f"REPAIR {panel.id}: falta el material {panel.material}")
        return

    if kind is ActionKind.ACTIVATE:
        index = spec.station_index.get(action.target or "")
        if index is None:
            raise IllegalActionError(f"ACTIVATE: estación desconocida {action.target}")
        station = spec.stations[index]
        if state.stations[index] == 1:
            raise IllegalActionError(f"ACTIVATE {station.id}: ya está ONLINE")
        if station.zone != state.pos:
            raise IllegalActionError(f"ACTIVATE {station.id}: el robot no está en {station.zone}")
        for p in station.required_panels:
            if state.panels[p] == 0:
                raise IllegalActionError(
                    f"ACTIVATE {station.id}: el panel {spec.panels[p].id} sigue dañado"
                )
        for s in station.required_stations:
            if state.stations[s] == 0:
                raise IllegalActionError(
                    f"ACTIVATE {station.id}: la estación {spec.stations[s].id} está OFFLINE"
                )
        return

    if kind is ActionKind.RECHARGE:
        if spec.chargers.get(state.pos) is None:
            raise IllegalActionError(f"RECHARGE: la zona {state.pos} no tiene cargador")
        if state.battery >= spec.battery_max:
            raise IllegalActionError("RECHARGE: la batería ya está llena")
        return

    raise IllegalActionError(f"Acción desconocida: {action.kind}")


def _slot_of(spec: WorldSpec, state: State, action: Action, *, expected: str) -> int:
    """Resuelve el slot de O afectado por PICKUP/DROP y valida su posición."""

    slot = action.slot
    if slot is None:
        if action.item is None:
            raise IllegalActionError(f"{action.kind.value}: no indica objeto")
        slot = _find_slot(spec, state, action.item, expected)
        if slot is None:
            raise IllegalActionError(
                f"{action.kind.value} {action.item}: no está en {expected}"
            )
        return slot

    if not 0 <= slot < len(spec.items):
        raise IllegalActionError(f"{action.kind.value}: slot inválido {slot}")
    if state.objects[slot] != expected:
        # La canonicalización puede haber permutado slots dentro de una clase
        # fungible; se acepta cualquier unidad equivalente en la posición pedida.
        alternative = _find_slot(spec, state, spec.items[slot].name, expected)
        if alternative is None:
            raise IllegalActionError(
                f"{action.kind.value} {spec.items[slot].name}: no está en {expected}"
            )
        return alternative
    return slot


def _apply(spec: WorldSpec, state: State, action: Action) -> State:
    """Efectos de la acción. Asume que la acción ya fue validada.

    Frame problem: toda variable no mencionada explícitamente conserva su valor.
    """

    kind = action.kind
    battery = state.battery - action.cost

    if kind is ActionKind.MOVE:
        # No toca O, P ni R: la tupla O del padre ya está canonicalizada.
        return build_state(
            spec,
            pos=action.target or state.pos,
            battery=battery,
            doors=state.doors,
            panels=state.panels,
            stations=state.stations,
            objects=state.objects,
            objects_canonical=True,
        )

    if kind is ActionKind.PICKUP:
        slot = _slot_of(spec, state, action, expected=state.pos)
        objects = list(state.objects)
        objects[slot] = IN_INVENTORY
        return build_state(
            spec,
            pos=state.pos,
            battery=battery,
            doors=state.doors,
            panels=state.panels,
            stations=state.stations,
            objects=tuple(objects),
        )

    if kind is ActionKind.DROP:
        slot = _slot_of(spec, state, action, expected=IN_INVENTORY)
        objects = list(state.objects)
        objects[slot] = state.pos
        return build_state(
            spec,
            pos=state.pos,
            battery=battery,
            doors=state.doors,
            panels=state.panels,
            stations=state.stations,
            objects=tuple(objects),
        )

    if kind is ActionKind.OPEN_DOOR:
        index = spec.door_index[action.target or ""]
        doors = list(state.doors)
        doors[index] = 1
        return build_state(
            spec,
            pos=state.pos,
            battery=battery,
            doors=tuple(doors),
            panels=state.panels,
            stations=state.stations,
            objects=state.objects,
        )

    if kind is ActionKind.REPAIR:
        index = spec.panel_index[action.target or ""]
        panel = spec.panels[index]
        panels = list(state.panels)
        panels[index] = 1
        objects = list(state.objects)
        if panel.material is not None:
            # El MATERIAL se consume y libera capacidad; la HERRAMIENTA no.
            slot = _find_slot(spec, state, panel.material, IN_INVENTORY)
            if slot is None:  # pragma: no cover - _validate ya lo garantiza
                raise IllegalActionError(f"REPAIR {panel.id}: falta el material {panel.material}")
            objects[slot] = USED
        return build_state(
            spec,
            pos=state.pos,
            battery=battery,
            doors=state.doors,
            panels=tuple(panels),
            stations=state.stations,
            objects=tuple(objects),
        )

    if kind is ActionKind.ACTIVATE:
        index = spec.station_index[action.target or ""]
        stations = list(state.stations)
        stations[index] = 1
        return build_state(
            spec,
            pos=state.pos,
            battery=battery,
            doors=state.doors,
            panels=state.panels,
            stations=tuple(stations),
            objects=state.objects,
            objects_canonical=True,  # E no interviene en la canonicalización de O
        )

    if kind is ActionKind.RECHARGE:
        # El costo se paga ANTES de recargar y luego la batería queda al máximo.
        return build_state(
            spec,
            pos=state.pos,
            battery=spec.battery_max,
            doors=state.doors,
            panels=state.panels,
            stations=state.stations,
            objects=state.objects,
            objects_canonical=True,
        )

    raise IllegalActionError(f"Acción desconocida: {action.kind}")


def successors(spec: WorldSpec, state: State) -> Iterator[tuple[Action, State]]:
    """Pares (acción, estado sucesor) para expandir un nodo en Graph Search."""

    for action in applicable_actions(spec, state):
        yield action, _apply(spec, state, action)
