"""Estado del agente: s = ⟨pos, b, P, R, E, O⟩.

Referencia: `project/design.md` — §Estado, §Relevancia y §Canonicalización del
Estado Sucesor.

Puntos clave implementados aquí:

* El estado es **inmutable y canónico** (tuplas ordenadas), por lo que sirve
  directamente como clave de tabla hash en Graph Search.
* Igualdad de estados: `s1 == s2` ⟺ coinciden pos, b, P, R, E y O.
* `physical_key()` devuelve la **configuración física** ⟨pos, P, R, E, O⟩ *sin*
  la batería: es la clave con la que `CLOSED` aplica la dominancia de batería.
* Canonicalización: olvido de posiciones muertas (`@OLVIDADO`) y ordenamiento de
  los objetos intercambiables dentro de su clase de equivalencia.
"""

from __future__ import annotations

from typing import NamedTuple

from .constants import FORGOTTEN, IN_INVENTORY, NON_SPATIAL, ItemKind
from .world import ItemSpec, WorldSpec

#: Tipo de la clave física usada por CLOSED (excluye la batería).
PhysicalKey = tuple[str, tuple[int, ...], tuple[int, ...], tuple[int, ...], tuple[str, ...]]


class State(NamedTuple):
    """s = ⟨pos, b, P, R, E, O⟩ — estado del mundo, no del nodo de búsqueda.

    Se implementa como `NamedTuple` porque design.md exige estructuras canónicas
    e inmutables: da hash y comparación por valor gratis y hace que el estado sea
    usable directamente como clave de la tabla `CLOSED`.

    La batería se declara al final —y no en la segunda posición como en la
    notación ⟨pos, b, …⟩— para que la configuración física sea exactamente el
    prefijo `self[:5]`, que es lo que indexa `CLOSED`.

    g(n), el nodo padre y la acción aplicada pertenecen al historial de búsqueda
    y viven en `search._Node`, nunca aquí (design.md §Historial de búsqueda).
    """

    pos: str
    doors: tuple[int, ...]     # P: 0 cerrada, 1 abierta
    panels: tuple[int, ...]    # R: 0 pendiente, 1 reparado
    stations: tuple[int, ...]  # E: 0 OFFLINE, 1 ONLINE
    objects: tuple[str, ...]   # O: zona | @EN_INVENTARIO | @USADO | @OLVIDADO
    battery: int               # b ∈ [0, battery_max]

    def physical_key(self) -> PhysicalKey:
        """⟨pos, P, R, E, O⟩ — configuración física sin batería."""
        return self[:5]


# ---------------------------------------------------------------------------
# Relevancia (design.md §Relevancia: objetos que ya no cambian a futuro)
# ---------------------------------------------------------------------------


def useful_units(
    spec: WorldSpec, item: ItemSpec, doors: tuple[int, ...], panels: tuple[int, ...]
) -> int:
    """Cuántas unidades de la clase de `item` pueden todavía servir para algo.

    * MATERIAL: una unidad por cada panel pendiente que lo exige (se consume).
    * LLAVE / HERRAMIENTA: 1 si queda alguna puerta/panel pendiente que sirva,
      porque son reutilizables y basta con una.
    * 0 ⟹ el objeto es irrelevante para siempre: P y R solo crecen de 0 a 1, así
      que la irrelevancia es monótona (nunca se «des-olvida» un objeto).
    """

    if item.kind is ItemKind.MATERIAL:
        return sum(1 for p in item.panels_served if panels[p] == 0)
    for d in item.doors_served:
        if doors[d] == 0:
            return 1
    for p in item.panels_served:
        if panels[p] == 0:
            return 1
    return 0


def relevance_vector(
    spec: WorldSpec, doors: tuple[int, ...], panels: tuple[int, ...]
) -> tuple[int, ...]:
    """`useful_units` de todos los objetos, memorizado por (P, R).

    La relevancia solo depende de P y R, que tienen pocos valores alcanzables;
    memorizarla evita recalcularla en cada sucesor generado.
    """

    cache = spec.relevance_cache
    key = (doors, panels)
    vector = cache.get(key)
    if vector is None:
        vector = tuple(useful_units(spec, item, doors, panels) for item in spec.items)
        cache[key] = vector
    return vector


def carried_units(spec: WorldSpec, state: State, eq_class: str) -> int:
    """Unidades de una clase de equivalencia que el robot lleva encima."""
    objects = state.objects
    return sum(1 for i in spec.class_slots[eq_class] if objects[i] == IN_INVENTORY)


def inventory_slots(spec: WorldSpec, state: State) -> tuple[int, ...]:
    return tuple(i for i, value in enumerate(state.objects) if value == IN_INVENTORY)


def carried_weight(spec: WorldSpec, state: State) -> int:
    items = spec.items
    return sum(
        items[i].weight for i, value in enumerate(state.objects) if value == IN_INVENTORY
    )


def free_capacity(spec: WorldSpec, state: State) -> int:
    """Espacio disponible: variable *derivada*, no almacenada (design.md §Deriva)."""
    return spec.cargo_capacity - carried_weight(spec, state)


# ---------------------------------------------------------------------------
# Canonicalización
# ---------------------------------------------------------------------------


def canonical_objects(
    spec: WorldSpec,
    objects: tuple[str, ...],
    doors: tuple[int, ...],
    panels: tuple[int, ...],
) -> tuple[str, ...]:
    """Aplica el olvido de posiciones muertas y ordena las clases fungibles.

    1. **Olvido (`@OLVIDADO`)**: si un objeto está en el suelo y ya no puede
       servir a ninguna puerta/panel pendiente, su zona concreta es información
       muerta — la poda de `PICKUP` obsoleto impide volver a recogerlo — y se
       reemplaza por la constante `@OLVIDADO`. Esto colapsa en un solo estado
       todas las variantes de «dónde quedó tirado un objeto inútil».
       Nota: solo se olvidan posiciones *del suelo*. Un objeto irrelevante que
       sigue `@EN_INVENTARIO` conserva su valor porque todavía ocupa capacidad.
    2. **Orden canónico**: dentro de una clase de objetos intercambiables (p. ej.
       dos unidades de `FUSE`) las posiciones se ordenan, de modo que dos
       permutaciones de la misma situación física son el mismo estado
       (design.md §Ruptura de Garantías, punto 2 «estados mal canonicalizados»).
    """

    relevance = relevance_vector(spec, doors, panels)
    values: list[str] | None = None

    for index, value in enumerate(objects):
        if value in NON_SPATIAL or relevance[index] > 0:
            continue
        if values is None:
            values = list(objects)
        values[index] = FORGOTTEN

    for group in spec.fungible_groups:
        current = [(values or objects)[i] for i in group]
        ordered = sorted(current)
        if ordered != current:
            if values is None:
                values = list(objects)
            for slot, value in zip(group, ordered):
                values[slot] = value

    return tuple(values) if values is not None else objects


def build_state(
    spec: WorldSpec,
    *,
    pos: str,
    battery: int,
    doors: tuple[int, ...],
    panels: tuple[int, ...],
    stations: tuple[int, ...],
    objects: tuple[str, ...],
    objects_canonical: bool = False,
) -> State:
    """Constructor canónico: única puerta de entrada para crear estados.

    `objects_canonical=True` es una optimización, no una excepción a la regla:
    la canonicalización de O solo depende de (O, P, R), así que si la acción no
    tocó ninguno de los tres, la tupla que ya traía el padre sigue siendo la
    forma canónica y volver a calcularla daría exactamente lo mismo.
    """

    return State(
        pos,
        doors,
        panels,
        stations,
        objects if objects_canonical else canonical_objects(spec, objects, doors, panels),
        # Invariante de batería: b ∈ [0, battery_max] (design.md §Canonicalización).
        max(0, min(spec.battery_max, battery)),
    )


def initial_state(spec: WorldSpec) -> State:
    """s₀ construido desde el escenario."""

    return build_state(
        spec,
        pos=spec.start_zone,
        battery=spec.battery_start,
        doors=tuple(1 if d.initially_open else 0 for d in spec.doors),
        panels=tuple(1 if p.initially_ok else 0 for p in spec.panels),
        stations=tuple(1 if s.initially_online else 0 for s in spec.stations),
        objects=tuple(item.start for item in spec.items),
    )


# ---------------------------------------------------------------------------
# Prueba de meta (design.md §Prueba de meta)
# ---------------------------------------------------------------------------


def is_goal(spec: WorldSpec, state: State) -> bool:
    """Goal(s) ⟺ ∀ j ∈ Estaciones_Objetivo, E_j == 1.

    No se exige nada sobre pos, b, P, R ni O: las puertas y los paneles son
    medios, no fines.
    """
    stations = state.stations
    return all(stations[j] == 1 for j in spec.goal_stations)


# ---------------------------------------------------------------------------
# Utilidades de depuración
# ---------------------------------------------------------------------------


def describe_state(spec: WorldSpec, state: State) -> str:
    inventory = [spec.items[i].name for i in inventory_slots(spec, state)]
    open_doors = [d.id for i, d in enumerate(spec.doors) if state.doors[i] == 1]
    ok_panels = [p.id for i, p in enumerate(spec.panels) if state.panels[i] == 1]
    online = [s.id for i, s in enumerate(spec.stations) if state.stations[i] == 1]
    return (
        f"pos={state.pos} b={state.battery} "
        f"inv={inventory or '-'} doors={open_doors or '-'} "
        f"panels={ok_panels or '-'} stations={online or '-'}"
    )
