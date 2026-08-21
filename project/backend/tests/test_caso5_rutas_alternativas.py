"""Caso 5 — Rutas alternativas.

    «Debe existir al menos una situación en la que puedan alcanzarse las mismas
    condiciones del mundo mediante diferentes rutas. La solución debe manejar
    correctamente esas rutas y conservar la alternativa que corresponda a la
    estrategia de búsqueda seleccionada y a su función de costo.»

Escenario: `caso5_rutas_alternativas.json` (variante). Diamante A→B→G y A→C→G
con el mismo número de acciones (6) y el mismo estado final del mundo:

    robot en G · PANEL_G reparado · TORRETA ONLINE · LLAVE_INGLESA en inventario
    · PIEZA consumida

Las dos rutas son ejecutables con la batería disponible; lo único que cambia es
el costo (10 por B, 16 por C). Así el test aísla el criterio: si el motor
devuelve la ruta B, es por g(n) y no porque la otra fuera ilegal o inalcanzable.

`scenario.json` también tiene rutas alternativas a Z5 (por DOOR3 con costo 3, o
por el corredor Z2→Z5 de costo 12) y se corrobora al final, pero ahí las dos
rutas dejan el mundo en estados distintos —una abre DOOR3— así que la variante
es la que demuestra la propiedad en su forma estricta.
"""

from __future__ import annotations

from _harness import (  # noqa: E402
    activate,
    info,
    move,
    ok,
    pickup,
    plan_moves,
    repair,
    solved,
    spec_of,
    title,
)

from agent import ActionKind, is_goal, replay_plan  # noqa: E402

ESCENARIO = "caso5_rutas_alternativas.json"


def _rutas(spec):
    comun_inicio = [pickup(spec, "LLAVE_INGLESA"), pickup(spec, "PIEZA")]
    comun_final = [repair(spec, "PANEL_G"), activate(spec, "TORRETA")]
    por_b = comun_inicio + [move(spec, "A", "B"), move(spec, "B", "G")] + comun_final
    por_c = comun_inicio + [move(spec, "A", "C"), move(spec, "C", "G")] + comun_final
    return por_b, por_c


def test_las_dos_rutas_llevan_al_mismo_estado_del_mundo() -> None:
    spec = spec_of(ESCENARIO)
    por_b, por_c = _rutas(spec)

    estado_b, costo_b = replay_plan(spec, por_b)
    estado_c, costo_c = replay_plan(spec, por_c)

    assert is_goal(spec, estado_b) and is_goal(spec, estado_c)
    assert len(por_b) == len(por_c) == 6
    assert estado_b.physical_key() == estado_c.physical_key()
    assert costo_b == 10 and costo_c == 16

    info(f"ruta por B: {plan_moves(tuple(por_b))}  →  {len(por_b)} acciones, costo {costo_b}")
    info(f"ruta por C: {plan_moves(tuple(por_c))}  →  {len(por_c)} acciones, costo {costo_c}")
    info(f"configuración física final (idéntica): {estado_b.physical_key()}")
    ok("dos rutas legales distintas alcanzan exactamente las mismas condiciones del mundo")


def test_la_ruta_cara_queda_dominada() -> None:
    """Misma configuración física, menos batería y más costo → se descarta."""

    spec = spec_of(ESCENARIO)
    por_b, por_c = _rutas(spec)
    estado_b, costo_b = replay_plan(spec, por_b)
    estado_c, costo_c = replay_plan(spec, por_c)

    domina_b = estado_b.battery >= estado_c.battery and costo_b <= costo_c
    assert domina_b
    assert estado_b.battery > estado_c.battery
    assert estado_b != estado_c  # difieren solo en b

    info(f"por B: b={estado_b.battery}, g={costo_b}")
    info(f"por C: b={estado_c.battery}, g={costo_c}")
    ok("la ruta por B domina a la ruta por C (design.md §Principio de Dominancia)")


def test_ucs_conserva_la_ruta_de_menor_costo() -> None:
    spec, resultado = solved(ESCENARIO)
    por_b, _ = _rutas(spec)
    _, costo_b = replay_plan(spec, por_b)

    assert resultado.solution_found
    assert resultado.total_cost == costo_b == 10
    assert plan_moves(resultado.plan) == "A -> B -> G"
    assert all(a.target != "C" for a in resultado.plan if a.kind is ActionKind.MOVE)

    info(f"plan devuelto ({resultado.total_cost}): "
         + " | ".join(a.describe() for a in resultado.plan))
    ok("UCS conserva la ruta barata y descarta la cara, coherente con g(n)")


def test_corroboracion_en_scenario_json() -> None:
    """En la instancia oficial hay dos accesos a Z5 y el motor toma el barato."""

    spec, resultado = solved()
    movimientos = [a for a in resultado.plan if a.kind is ActionKind.MOVE]

    por_corredor_caro = [a for a in movimientos if a.origin == "Z2" and a.target == "Z5"]
    entradas_a_z5 = [a.origin for a in movimientos if a.target == "Z5"]

    assert por_corredor_caro == []
    assert set(entradas_a_z5) == {"Z4"}

    info(f"recorrido: {plan_moves(resultado.plan)}")
    info("accesos a Z5 disponibles: Z2->Z5 (costo 12, sin puerta) y Z4->Z5 (costo 3, exige DOOR3)")
    info(f"entradas a Z5 usadas por el plan: {entradas_a_z5}")
    ok("prefiere abrir DOOR3 y entrar por Z4 antes que pagar el corredor de 12")


def main() -> None:
    title(f"CASO 5 — Rutas alternativas ({ESCENARIO} + scenario.json)")
    test_las_dos_rutas_llevan_al_mismo_estado_del_mundo()
    test_la_ruta_cara_queda_dominada()
    test_ucs_conserva_la_ruta_de_menor_costo()
    test_corroboracion_en_scenario_json()


if __name__ == "__main__":
    main()
    print("\nCaso 5: OK")
