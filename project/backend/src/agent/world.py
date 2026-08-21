"""Información estática del mundo: todo lo que NO se guarda en el estado.

Referencia: `project/design.md` — §«Qué información se deriva y NO se almacena».

`WorldSpec` es la tabla estática que el estado dinámico ⟨pos, b, P, R, E, O⟩
consulta pero no replica: grafo de corredores, qué llave abre qué puerta, qué
herramienta y qué material exige cada panel, el grafo de dependencias de las
estaciones, la clasificación LLAVE/HERRAMIENTA/MATERIAL, la capacidad de carga,
la batería máxima y los costos de acción.

Todos los valores provienen del escenario (`scenario.json`): aquí no hay ids,
costos ni cantidades codificados a mano.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .constants import (
    DEFAULT_ACTION_COSTS,
    DEFAULT_BATTERY_MAX,
    DEFAULT_CARGO_CAPACITY,
    IN_INVENTORY,
    ItemKind,
)


class ScenarioError(ValueError):
    """El escenario recibido es inconsistente o le falta información."""


# ---------------------------------------------------------------------------
# Descriptores estáticos
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Corridor:
    """Arista dirigida del grafo de movimiento."""

    to: str
    cost: int
    door: int | None  # índice en la tupla P, o None si el corredor es libre


@dataclass(frozen=True, slots=True)
class DoorSpec:
    id: str
    key: str | None            # nombre del objeto LLAVE requerido (None = sin llave)
    zones: tuple[str, ...]     # zonas desde las que se puede operar la puerta
    initially_open: bool


@dataclass(frozen=True, slots=True)
class PanelSpec:
    id: str
    zone: str
    tool: str | None       # herramienta requerida (no se consume)
    material: str | None   # tipo de material requerido (se consume)
    initially_ok: bool


@dataclass(frozen=True, slots=True)
class StationSpec:
    id: str
    zone: str
    required_panels: tuple[int, ...]    # índices en R
    required_stations: tuple[int, ...]  # índices en E
    initially_online: bool


@dataclass(frozen=True, slots=True)
class ItemSpec:
    """Un slot de la tupla O.

    `eq_class` implementa la exigencia del enunciado §2.2: los objetos del mismo
    tipo declarados equivalentes (los materiales) NO se distinguen con
    identificadores individuales. Dos unidades de `FUSE` comparten clase y el
    estado se canonicaliza ordenando sus posiciones.
    """

    index: int
    name: str                       # id de llave/herramienta o tipo de material
    kind: ItemKind
    weight: int
    eq_class: str
    doors_served: tuple[int, ...]   # puertas que este objeto puede abrir
    panels_served: tuple[int, ...]  # paneles que este objeto puede reparar
    start: str                      # zona inicial (o IN_INVENTORY)


@dataclass(frozen=True, slots=True)
class WorldSpec:
    """Modelo estático completo de una instancia del problema."""

    # --- topología ---
    zones: tuple[str, ...]
    adjacency: Mapping[str, tuple[Corridor, ...]]
    chargers: Mapping[str, str]  # zona -> id del cargador

    # --- elementos del entorno ---
    doors: tuple[DoorSpec, ...]
    panels: tuple[PanelSpec, ...]
    stations: tuple[StationSpec, ...]
    door_index: Mapping[str, int]
    panel_index: Mapping[str, int]
    station_index: Mapping[str, int]
    # Índices por zona: qué se puede operar estando en cada zona.
    doors_by_zone: Mapping[str, tuple[int, ...]]
    panels_by_zone: Mapping[str, tuple[int, ...]]
    stations_by_zone: Mapping[str, tuple[int, ...]]

    # --- objetos ---
    items: tuple[ItemSpec, ...]
    fungible_groups: tuple[tuple[int, ...], ...]  # clases con más de un slot
    class_slots: Mapping[str, tuple[int, ...]]
    slots_by_name: Mapping[str, tuple[int, ...]]

    # --- misión ---
    goal_stations: tuple[int, ...]
    useful_stations: frozenset[int]  # meta + cierre transitivo de prerrequisitos

    # --- robot y costos ---
    start_zone: str
    battery_start: int
    battery_max: int
    cargo_capacity: int
    cost_pickup: int
    cost_drop: int
    cost_interact: int
    cost_recharge: int

    #: Memoria de una función pura: (P, R) -> unidades útiles de cada objeto.
    #: Es caché, no estado del mundo; por eso queda fuera de repr/comparación.
    relevance_cache: dict = field(default_factory=dict, repr=False, compare=False)

    def zone_exists(self, zone: str) -> bool:
        return zone in self.adjacency


# ---------------------------------------------------------------------------
# Parseo del escenario
# ---------------------------------------------------------------------------


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ScenarioError(message)


def _as_list(scenario: Mapping[str, Any], key: str) -> Sequence[Mapping[str, Any]]:
    value = scenario.get(key) or []
    _require(isinstance(value, Sequence), f"'{key}' debe ser una lista")
    return value


def parse_scenario(scenario: Mapping[str, Any]) -> WorldSpec:
    """Traduce el JSON del escenario a la tabla estática `WorldSpec`."""

    _require(isinstance(scenario, Mapping), "el escenario debe ser un objeto JSON")

    # --- robot -------------------------------------------------------------
    robot = scenario.get("robot") or {}
    battery_max = int(robot.get("battery_max", DEFAULT_BATTERY_MAX))
    battery_start = int(robot.get("battery_start", battery_max))
    capacity = int(robot.get("cargo_capacity", DEFAULT_CARGO_CAPACITY))
    _require(battery_max > 0, "battery_max debe ser positivo")
    _require(capacity > 0, "cargo_capacity debe ser positivo")
    battery_start = max(0, min(battery_max, battery_start))

    # --- costos ------------------------------------------------------------
    costs = {**DEFAULT_ACTION_COSTS, **(scenario.get("action_costs") or {})}
    cost_pickup = int(costs["pickup"])
    cost_drop = int(costs["drop"])
    cost_interact = int(costs["interact"])
    cost_recharge = int(costs["recharge"])
    for name, value in (
        ("pickup", cost_pickup),
        ("drop", cost_drop),
        ("interact", cost_interact),
        ("recharge", cost_recharge),
    ):
        # UCS solo es completo/óptimo con costos estrictamente positivos
        # (design.md §Ruptura de Garantías Formales, punto 1).
        _require(value > 0, f"action_costs.{name} debe ser > 0 (recibido {value})")

    # --- zonas -------------------------------------------------------------
    zones = tuple(str(z["id"]) for z in _as_list(scenario, "zones"))
    _require(bool(zones), "el escenario no declara zonas")
    zone_set = set(zones)

    start_zone = str(robot.get("start", zones[0]))
    _require(start_zone in zone_set, f"la zona inicial {start_zone} no existe")

    # --- puertas -----------------------------------------------------------
    doors: list[DoorSpec] = []
    door_index: dict[str, int] = {}
    for raw in _as_list(scenario, "doors"):
        did = str(raw["id"])
        between = tuple(str(z) for z in (raw.get("between") or ()))
        for zone in between:
            _require(zone in zone_set, f"puerta {did}: zona desconocida {zone}")
        key = raw.get("key")
        door_index[did] = len(doors)
        doors.append(
            DoorSpec(
                id=did,
                key=str(key) if key else None,
                zones=between,
                initially_open=str(raw.get("state", "CLOSED")).upper() == "OPEN",
            )
        )

    # --- corredores --------------------------------------------------------
    adjacency: dict[str, list[Corridor]] = {z: [] for z in zones}
    for raw in _as_list(scenario, "corridors"):
        frm, to = str(raw["from"]), str(raw["to"])
        _require(frm in zone_set and to in zone_set, f"corredor {frm}->{to}: zona desconocida")
        cost = int(raw["cost"])
        _require(cost > 0, f"corredor {frm}->{to}: el costo debe ser > 0")
        door = raw.get("door")
        if door is not None:
            _require(str(door) in door_index, f"corredor {frm}->{to}: puerta desconocida {door}")
        adjacency[frm].append(
            Corridor(to=to, cost=cost, door=door_index[str(door)] if door else None)
        )

    # --- paneles -----------------------------------------------------------
    panels: list[PanelSpec] = []
    panel_index: dict[str, int] = {}
    for raw in _as_list(scenario, "panels"):
        pid = str(raw["id"])
        zone = str(raw["zone"])
        _require(zone in zone_set, f"panel {pid}: zona desconocida {zone}")
        requires = raw.get("requires") or {}
        panel_index[pid] = len(panels)
        panels.append(
            PanelSpec(
                id=pid,
                zone=zone,
                tool=str(requires["tool"]) if requires.get("tool") else None,
                material=str(requires["material"]) if requires.get("material") else None,
                initially_ok=str(raw.get("state", "DAMAGED")).upper() in ("OK", "REPAIRED"),
            )
        )

    # --- estaciones --------------------------------------------------------
    raw_stations = list(_as_list(scenario, "stations"))
    station_index = {str(raw["id"]): i for i, raw in enumerate(raw_stations)}
    stations: list[StationSpec] = []
    for raw in raw_stations:
        sid = str(raw["id"])
        zone = str(raw["zone"])
        _require(zone in zone_set, f"estación {sid}: zona desconocida {zone}")
        requires = raw.get("requires") or {}
        req_panels = []
        for pid in requires.get("panels_ok") or ():
            _require(str(pid) in panel_index, f"estación {sid}: panel desconocido {pid}")
            req_panels.append(panel_index[str(pid)])
        req_stations = []
        for other in requires.get("stations_online") or ():
            _require(str(other) in station_index, f"estación {sid}: estación desconocida {other}")
            req_stations.append(station_index[str(other)])
        stations.append(
            StationSpec(
                id=sid,
                zone=zone,
                required_panels=tuple(sorted(req_panels)),
                required_stations=tuple(sorted(req_stations)),
                initially_online=str(raw.get("state", "OFFLINE")).upper() == "ONLINE",
            )
        )

    # --- meta y cierre transitivo de estaciones útiles ----------------------
    goal_ids = (scenario.get("goal") or {}).get("stations_online") or ()
    goal_stations = []
    for sid in goal_ids:
        _require(str(sid) in station_index, f"goal: estación desconocida {sid}")
        goal_stations.append(station_index[str(sid)])
    goal_stations = tuple(sorted(set(goal_stations)))

    useful: set[int] = set()
    pending = list(goal_stations)
    while pending:
        idx = pending.pop()
        if idx in useful:
            continue
        useful.add(idx)
        pending.extend(stations[idx].required_stations)

    # --- índices por zona ---------------------------------------------------
    doors_by_zone: dict[str, list[int]] = {z: [] for z in zones}
    for i, door in enumerate(doors):
        for zone in door.zones:
            doors_by_zone[zone].append(i)
    panels_by_zone: dict[str, list[int]] = {z: [] for z in zones}
    for i, panel in enumerate(panels):
        panels_by_zone[panel.zone].append(i)
    stations_by_zone: dict[str, list[int]] = {z: [] for z in zones}
    for i, station in enumerate(stations):
        stations_by_zone[station.zone].append(i)

    # --- objetos (tupla O) --------------------------------------------------
    items = _build_items(scenario, zone_set, doors, panels)

    class_slots: dict[str, list[int]] = {}
    slots_by_name: dict[str, list[int]] = {}
    for item in items:
        class_slots.setdefault(item.eq_class, []).append(item.index)
        slots_by_name.setdefault(item.name, []).append(item.index)
    fungible_groups = tuple(
        tuple(slots) for slots in class_slots.values() if len(slots) > 1
    )

    # --- cargadores ---------------------------------------------------------
    chargers: dict[str, str] = {}
    for raw in _as_list(scenario, "chargers"):
        zone = str(raw["zone"])
        _require(zone in zone_set, f"cargador {raw.get('id')}: zona desconocida {zone}")
        chargers.setdefault(zone, str(raw.get("id", zone)))
    if not chargers:
        # Instancias que solo marcan la zona con `recharge: true`.
        for raw in _as_list(scenario, "zones"):
            if raw.get("recharge"):
                chargers.setdefault(str(raw["id"]), str(raw["id"]))

    return WorldSpec(
        zones=zones,
        adjacency={z: tuple(c) for z, c in adjacency.items()},
        chargers=chargers,
        doors=tuple(doors),
        panels=tuple(panels),
        stations=tuple(stations),
        door_index=door_index,
        panel_index=panel_index,
        station_index=station_index,
        doors_by_zone={k: tuple(v) for k, v in doors_by_zone.items()},
        panels_by_zone={k: tuple(v) for k, v in panels_by_zone.items()},
        stations_by_zone={k: tuple(v) for k, v in stations_by_zone.items()},
        items=items,
        fungible_groups=fungible_groups,
        class_slots={k: tuple(v) for k, v in class_slots.items()},
        slots_by_name={k: tuple(v) for k, v in slots_by_name.items()},
        goal_stations=goal_stations,
        useful_stations=frozenset(useful),
        start_zone=start_zone,
        battery_start=battery_start,
        battery_max=battery_max,
        cargo_capacity=capacity,
        cost_pickup=cost_pickup,
        cost_drop=cost_drop,
        cost_interact=cost_interact,
        cost_recharge=cost_recharge,
    )


def _build_items(
    scenario: Mapping[str, Any],
    zone_set: set[str],
    doors: Sequence[DoorSpec],
    panels: Sequence[PanelSpec],
) -> tuple[ItemSpec, ...]:
    """Construye la tupla O unificando llaves, herramientas y materiales.

    A cada slot se le precomputan las puertas y paneles a los que puede servir;
    de ahí sale la noción de *relevancia* usada por las podas y por el olvido de
    posiciones muertas (design.md §Relevancia).
    """

    items: list[ItemSpec] = []

    def add(name: str, kind: ItemKind, weight: int, start: str) -> None:
        served_doors = tuple(
            i for i, d in enumerate(doors) if d.key == name
        ) if kind is ItemKind.KEY else ()
        served_panels = tuple(
            i
            for i, p in enumerate(panels)
            if (kind is ItemKind.TOOL and p.tool == name)
            or (kind is ItemKind.MATERIAL and p.material == name)
        )
        items.append(
            ItemSpec(
                index=len(items),
                name=name,
                kind=kind,
                weight=weight,
                # Llaves y herramientas son únicas: cada una es su propia clase.
                # Los materiales comparten clase por tipo (son intercambiables).
                eq_class=name if kind is ItemKind.MATERIAL else f"#{name}",
                doors_served=served_doors,
                panels_served=served_panels,
                start=start,
            )
        )

    for raw in _as_list(scenario, "keys"):
        zone = str(raw["zone"])
        _require(zone in zone_set, f"llave {raw['id']}: zona desconocida {zone}")
        add(str(raw["id"]), ItemKind.KEY, int(raw.get("weight", 1)), zone)

    for raw in _as_list(scenario, "tools"):
        zone = str(raw["zone"])
        _require(zone in zone_set, f"herramienta {raw['id']}: zona desconocida {zone}")
        add(str(raw["id"]), ItemKind.TOOL, int(raw.get("weight", 1)), zone)

    for raw in _as_list(scenario, "materials"):
        zone = str(raw["zone"])
        mtype = str(raw.get("type", raw.get("id")))
        _require(zone in zone_set, f"material {mtype}: zona desconocida {zone}")
        count = int(raw.get("count", 1))
        _require(count >= 0, f"material {mtype}: count inválido {count}")
        weight = int(raw.get("weight", 1))
        for _ in range(count):
            add(mtype, ItemKind.MATERIAL, weight, zone)

    # Nota: una puerta cuya llave no existe, o un panel cuya herramienta o
    # material no existen, NO son errores de formato: describen un elemento del
    # entorno que nunca podrá resolverse. Si la meta depende de él, la búsqueda
    # lo reporta como FAILURE; si no, el plan simplemente lo ignora.

    for item in items:
        _require(
            item.start in zone_set or item.start == IN_INVENTORY,
            f"objeto {item.name}: posición inicial inválida {item.start}",
        )

    return tuple(items)
