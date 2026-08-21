"""Caso 3 — Costos diferentes.

    «Debe existir al menos una instancia donde la solución con menor cantidad de
    acciones no sea la solución de menor costo.»

Escenario: `caso3_costo_vs_pasos.json` (variante). En `scenario.json` el efecto
existe pero está enredado con llaves, materiales y recargas; la variante lo
aísla en un mapa de cuatro zonas donde la comparación es directa:

    atajo : A --20--> G           →  2 acciones, costo 22
    rodeo : A -1-> B -1-> C -1-> G →  4 acciones, costo  5

Los dos planes son legales y alcanzan la meta; `design.md` afirma que g(n) mide
batería consumida y no pasos, así que UCS debe devolver el rodeo.

Además se corrobora sobre `scenario.json`: el plan artesanal de `demo_plan.py`
usa **menos** pasos que el plan óptimo del motor y cuesta **más**.
"""

from __future__ import annotations

from _harness import (  # noqa: E402
    activate,
    info,
    move,
    ok,
    plan_moves,
    solved,
    spec_of,
    title,
)

from agent import ActionKind, is_goal, replay_plan  # noqa: E402

ESCENARIO = "caso3_costo_vs_pasos.json"


def test_ucs_prefiere_el_plan_barato_aunque_tenga_mas_acciones() -> None:
    spec, resultado = solved(ESCENARIO)

    assert resultado.solution_found
    assert resultado.total_cost == 5
    assert len(resultado.plan) == 4
    assert plan_moves(resultado.plan) == "A -> B -> C -> G"

    info(f"plan devuelto: {' | '.join(a.describe() for a in resultado.plan)}")
    info(f"acciones={len(resultado.plan)}  costo={resultado.total_cost}")
    ok("UCS devuelve el plan de 4 acciones y costo 5")


def test_el_plan_mas_corto_es_legal_pero_mas_caro() -> None:
    """El atajo existe, es ejecutable y alcanza la meta: solo es peor en costo."""

    spec = spec_of(ESCENARIO)
    _, resultado = solved(ESCENARIO)

    atajo = [move(spec, "A", "G"), activate(spec, "MANDO")]
    estado_final, costo_atajo = replay_plan(spec, atajo)

    assert is_goal(spec, estado_final)          # el atajo sí resuelve la misión
    assert len(atajo) < len(resultado.plan)     # y usa menos acciones
    assert costo_atajo > resultado.total_cost   # pero cuesta más

    info(f"atajo  : {len(atajo)} acciones, costo {costo_atajo}, meta={is_goal(spec, estado_final)}")
    info(f"óptimo : {len(resultado.plan)} acciones, costo {resultado.total_cost}")
    ok("menos acciones (2) ≠ menor costo (22 > 5): el motor optimiza g(n), no la longitud")


def test_ningun_plan_alternativo_baja_de_ese_costo() -> None:
    """Comprobación de optimalidad: el costo 5 es el mínimo real."""

    spec = spec_of(ESCENARIO)
    _, resultado = solved(ESCENARIO)

    alternativas = {
        "A->G (atajo)": [move(spec, "A", "G"), activate(spec, "MANDO")],
        "A->B->C->G": [
            move(spec, "A", "B"),
            move(spec, "B", "C"),
            move(spec, "C", "G"),
            activate(spec, "MANDO"),
        ],
        "A->B->C->G->A->G (rodeo absurdo)": [
            move(spec, "A", "B"),
            move(spec, "B", "C"),
            move(spec, "C", "G"),
            move(spec, "G", "A"),
            move(spec, "A", "G"),
            activate(spec, "MANDO"),
        ],
    }
    for etiqueta, plan in alternativas.items():
        estado, costo = replay_plan(spec, plan)
        marca = "meta" if is_goal(spec, estado) else "no meta"
        info(f"{etiqueta:<34} {len(plan)} acciones, costo {costo:>3} ({marca})")
        if is_goal(spec, estado):
            assert costo >= resultado.total_cost

    ok("ningún plan alternativo legal baja de 5")


def test_corroboracion_en_scenario_json() -> None:
    """El mismo fenómeno en la instancia oficial, contra el plan artesanal."""

    from demo_plan import build_demo_plan  # noqa: E402
    from simulator import goal_satisfied, simulate  # noqa: E402

    from _harness import load

    escenario = load()
    _, resultado = solved()

    demo = build_demo_plan(escenario)
    final = simulate(escenario, demo["steps"])          # el plan artesanal es legal
    assert goal_satisfied(escenario, final)

    assert len(demo["steps"]) < len(resultado.plan)     # menos pasos
    assert demo["total_cost"] > resultado.total_cost    # más costo

    info(f"demo_plan.py : {len(demo['steps'])} pasos, costo {demo['total_cost']}")
    info(f"motor (UCS)  : {len(resultado.plan)} acciones, costo {resultado.total_cost}")
    ok("en scenario.json el plan más corto (34 pasos) también es más caro (99 > 80)")


def main() -> None:
    title(f"CASO 3 — Costos diferentes ({ESCENARIO} + scenario.json)")
    test_ucs_prefiere_el_plan_barato_aunque_tenga_mas_acciones()
    test_el_plan_mas_corto_es_legal_pero_mas_caro()
    test_ningun_plan_alternativo_baja_de_ese_costo()
    test_corroboracion_en_scenario_json()


if __name__ == "__main__":
    main()
    print("\nCaso 3: OK")
