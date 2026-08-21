"""Caso 1 — Estados equivalentes.

    «Dos configuraciones físicamente equivalentes deben producir el mismo
    estado lógico, aunque hayan sido generadas mediante historias diferentes.»

Escenario: `scenario.json` **tal cual**. No hace falta variante porque la
instancia oficial ya trae las tres fuentes de equivalencia que define
`design.md`:

* dos llaves que mueren al abrirse su puerta  → olvido de posiciones (`@OLVIDADO`)
* dos unidades de `FUSE` intercambiables       → clase de equivalencia fungible
* acciones conmutativas (dos `PICKUP` en la misma zona)

Las historias se ejecutan con `Result(s, a)`, que exige la legalidad física del
mundo (no las podas): lo que se compara es el estado que produce cada historia.
"""

from __future__ import annotations

from _harness import (  # noqa: E402
    describe_plan,
    drop,
    info,
    move,
    ok,
    open_door,
    pickup,
    slot_of,
    spec_of,
    title,
)

from agent import IN_INVENTORY, build_state, initial_state, replay_plan  # noqa: E402


def test_historias_distintas_mismo_estado_por_olvido() -> None:
    """Dos objetos muertos soltados en zonas intercambiadas colapsan."""

    spec = spec_of()

    # Ambas historias abren DOOR1 y DOOR2 (con lo que KEY1 y KEY2 quedan
    # muertas) y sueltan una llave en Z2 y la otra en Z3. Lo único que cambia
    # es CUÁL llave queda en CUÁL zona.
    prefijo = [
        pickup(spec, "KEY1"),
        open_door(spec, "DOOR1"),
        move(spec, "Z1", "Z2"),
        pickup(spec, "KEY2"),
        open_door(spec, "DOOR2"),
    ]
    historia_a = prefijo + [
        drop(spec, "KEY1", "Z2"),
        move(spec, "Z2", "Z3"),
        drop(spec, "KEY2", "Z3"),
    ]
    historia_b = prefijo + [
        drop(spec, "KEY2", "Z2"),
        move(spec, "Z2", "Z3"),
        drop(spec, "KEY1", "Z3"),
    ]

    estado_a, costo_a = replay_plan(spec, historia_a)
    estado_b, costo_b = replay_plan(spec, historia_b)

    assert historia_a != historia_b
    assert costo_a == costo_b
    assert estado_a == estado_b
    assert hash(estado_a) == hash(estado_b)
    assert len({estado_a, estado_b}) == 1
    assert estado_a.physical_key() == estado_b.physical_key()

    info(f"historia A: {describe_plan(spec, tuple(historia_a[5:]))}")
    info(f"historia B: {describe_plan(spec, tuple(historia_b[5:]))}")
    info(f"O canónica en ambas: {estado_a.objects[:3]}  (costo {costo_a} en las dos)")
    ok("dos historias distintas → mismo estado lógico (mismo hash, un solo elemento en el set)")


def test_el_olvido_solo_colapsa_objetos_muertos() -> None:
    """El contraste: si las llaves siguen vivas, la zona SÍ distingue."""

    spec = spec_of()
    s0 = initial_state(spec)
    k1, k2 = slot_of(spec, "KEY1"), slot_of(spec, "KEY2")

    def con_llaves(zona_k1: str, zona_k2: str, puertas: tuple[int, ...]):
        objetos = list(s0.objects)
        objetos[k1] = zona_k1
        objetos[k2] = zona_k2
        return build_state(
            spec,
            pos="Z3",
            battery=30,
            doors=puertas,
            panels=s0.panels,
            stations=s0.stations,
            objects=tuple(objetos),
        )

    muertas_a = con_llaves("Z2", "Z3", (1, 1, 0))
    muertas_b = con_llaves("Z3", "Z2", (1, 1, 0))
    vivas_a = con_llaves("Z2", "Z3", (0, 0, 0))
    vivas_b = con_llaves("Z3", "Z2", (0, 0, 0))

    assert muertas_a == muertas_b
    assert vivas_a != vivas_b

    info(f"puertas abiertas → llaves muertas : {muertas_a.objects[:2]} == {muertas_b.objects[:2]}")
    info(f"puertas cerradas → llaves vivas   : {vivas_a.objects[:2]} != {vivas_b.objects[:2]}")
    ok("el olvido colapsa solo posiciones muertas; una llave viva sigue distinguiendo estados")


def test_unidades_fungibles_del_mismo_material() -> None:
    """Llevar «el fusible A» o «el fusible B» es el mismo estado."""

    spec = spec_of()
    s0 = initial_state(spec)
    fusibles = spec.class_slots["FUSE"]
    assert len(fusibles) == 2, "scenario.json declara FUSE con count 2"

    def con_fusible_en_inventario(slot: int):
        objetos = list(s0.objects)
        objetos[slot] = IN_INVENTORY
        return build_state(
            spec,
            pos="Z2",
            battery=50,
            doors=s0.doors,
            panels=s0.panels,
            stations=s0.stations,
            objects=tuple(objetos),
        )

    primero = con_fusible_en_inventario(fusibles[0])
    segundo = con_fusible_en_inventario(fusibles[1])

    assert primero == segundo
    info(f"slots FUSE = {fusibles}; O canónica en ambos casos: {primero.objects[6:8]}")
    ok("dos unidades del mismo material no se distinguen artificialmente")


def test_acciones_conmutativas() -> None:
    """Recoger KEY2 y FUSE en cualquier orden lleva al mismo estado."""

    spec = spec_of()
    prefijo = [pickup(spec, "KEY1"), open_door(spec, "DOOR1"), move(spec, "Z1", "Z2")]

    orden_1 = prefijo + [pickup(spec, "KEY2"), pickup(spec, "FUSE")]
    orden_2 = prefijo + [pickup(spec, "FUSE"), pickup(spec, "KEY2")]

    estado_1, costo_1 = replay_plan(spec, orden_1)
    estado_2, costo_2 = replay_plan(spec, orden_2)

    assert orden_1 != orden_2
    assert estado_1 == estado_2 and costo_1 == costo_2
    info(f"PICKUP KEY2 + PICKUP FUSE  ==  PICKUP FUSE + PICKUP KEY2  (costo {costo_1})")
    ok("el orden de acciones conmutativas no crea estados distintos")


def main() -> None:
    title("CASO 1 — Estados equivalentes (scenario.json, sin variante)")
    test_historias_distintas_mismo_estado_por_olvido()
    test_el_olvido_solo_colapsa_objetos_muertos()
    test_unidades_fungibles_del_mismo_material()
    test_acciones_conmutativas()


if __name__ == "__main__":
    main()
    print("\nCaso 1: OK")
