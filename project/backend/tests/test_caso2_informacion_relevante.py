"""Caso 2 — Información relevante.

    «Dos configuraciones que difieran en información que puede cambiar las
    acciones futuras deben mantenerse como estados diferentes.»

Escenario: `caso2_bateria_relevante.json` (variante). `scenario.json` no sirve
tal cual para *demostrar* la propiedad: hay que poder llegar a una misma
configuración física con dos baterías distintas y que solo una de ellas permita
continuar la misión. La variante lo construye con un diamante mínimo:

    A --2--> B                (directo:   g=2,  b=10)
    A --2--> C(cargador) --2--> B   (con recarga: g=7,  b=38)
    B --30--> G               (solo el nodo recargado puede cruzarlo)

Los dos nodos en B tienen la MISMA configuración física ⟨pos, P, R, E, O⟩ y
ninguno domina al otro (b₁ ≥ b₂ pero g(n₁) > g(n₂), design.md §Principio de
Dominancia). Si la búsqueda los colapsara, la misión quedaría sin solución.
"""

from __future__ import annotations

from _harness import (  # noqa: E402
    info,
    move,
    ok,
    recharge,
    solved,
    spec_of,
    title,
)

from agent import ActionKind, applicable_actions, replay_plan  # noqa: E402

ESCENARIO = "caso2_bateria_relevante.json"


def _dos_rutas_a_b():
    spec = spec_of(ESCENARIO)
    directa = [move(spec, "A", "B")]
    recargando = [move(spec, "A", "C"), recharge(spec, "C"), move(spec, "C", "B")]
    estado_directo, g_directo = replay_plan(spec, directa)
    estado_recargado, g_recargado = replay_plan(spec, recargando)
    return spec, (estado_directo, g_directo), (estado_recargado, g_recargado)


def test_misma_configuracion_fisica_distinta_bateria() -> None:
    spec, (directo, g_directo), (recargado, g_recargado) = _dos_rutas_a_b()

    assert directo.physical_key() == recargado.physical_key()
    assert directo != recargado
    assert directo.battery == 10 and recargado.battery == 38
    assert g_directo == 2 and g_recargado == 7

    info(f"ruta directa    : g={g_directo}, b={directo.battery}")
    info(f"ruta con recarga: g={g_recargado}, b={recargado.battery}")
    info(f"clave física de CLOSED (idéntica): {directo.physical_key()}")
    ok("misma ⟨pos,P,R,E,O⟩ y distinta batería → estados DISTINTOS (b forma parte del estado)")


def test_ninguno_domina_al_otro() -> None:
    """b₁ ≥ b₂ pero g(n₁) > g(n₂): la regla de dominancia no aplica."""

    spec, (directo, g_directo), (recargado, g_recargado) = _dos_rutas_a_b()

    domina_recargado = recargado.battery >= directo.battery and g_recargado <= g_directo
    domina_directo = directo.battery >= recargado.battery and g_directo <= g_recargado

    assert recargado.battery > directo.battery
    assert g_recargado > g_directo
    assert not domina_recargado and not domina_directo

    info(f"recargado domina a directo: {domina_recargado} (más batería, pero también más costo)")
    info(f"directo domina a recargado: {domina_directo} (menos costo, pero menos batería)")
    ok("ninguno domina al otro → CLOSED no puede descartar ninguno de los dos")


def test_la_bateria_cambia_las_acciones_futuras() -> None:
    """La diferencia de b no es cosmética: habilita un MOVE que el otro no tiene."""

    spec, (directo, _), (recargado, _) = _dos_rutas_a_b()

    def mueve_a_g(estado) -> bool:
        return any(
            a.kind is ActionKind.MOVE and a.target == "G"
            for a in applicable_actions(spec, estado)
        )

    assert not mueve_a_g(directo)
    assert mueve_a_g(recargado)

    info(f"Applicable(b=10) = {[a.describe() for a in applicable_actions(spec, directo)]}")
    info(f"MOVE B->G (costo 30) disponible con b=38: {mueve_a_g(recargado)}")
    ok("la batería cambia el conjunto de acciones futuras: es información relevante")


def test_la_mision_se_resuelve_gracias_a_esa_distincion() -> None:
    spec, resultado = solved(ESCENARIO)

    assert resultado.solution_found
    assert resultado.total_cost == 39
    zonas = [a.target for a in resultado.plan if a.kind is ActionKind.MOVE]
    assert zonas == ["C", "B", "G"]
    assert any(a.kind is ActionKind.RECHARGE for a in resultado.plan)

    info(f"plan óptimo ({resultado.total_cost}): "
         + " | ".join(a.describe() for a in resultado.plan))
    ok("la misión solo tiene solución porque el nodo con más batería sobrevive en OPEN")


def main() -> None:
    title(f"CASO 2 — Información relevante ({ESCENARIO})")
    test_misma_configuracion_fisica_distinta_bateria()
    test_ninguno_domina_al_otro()
    test_la_bateria_cambia_las_acciones_futuras()
    test_la_mision_se_resuelve_gracias_a_esa_distincion()


if __name__ == "__main__":
    main()
    print("\nCaso 2: OK")
