"""Caso 4 — Sin solución.

    «El agente debe terminar correctamente y devolver FAILURE cuando la misión
    no pueda completarse. No se aceptará una ejecución que quede atrapada
    indefinidamente explorando el espacio de estados.»

Escenarios (dos variantes, para cubrir los dos regímenes de terminación):

1. `caso4_dependencia_circular.json` — NUCLEO exige RESPALDO ONLINE y RESPALDO
   exige NUCLEO ONLINE. Todo lo demás del mapa **sí** es alcanzable (llave,
   puerta, herramienta, material, panel reparable, cargador), así que la
   búsqueda tiene que **agotar un espacio de estados real** antes de concluir.
   Es el caso interesante: demuestra que `OPEN` se vacía y el motor devuelve
   FAILURE, en vez de girar para siempre.
2. `caso4_bateria_insuficiente.json` — el único corredor cuesta 30 y el robot
   arranca con 10, sin cargadores: `Applicable(s₀)` es vacío y `OPEN` se vacía
   en la primera extracción.

`scenario.json` no sirve tal cual: tiene solución. Por eso hacen falta variantes.

La terminación se demuestra de dos maneras: midiendo el tiempo real de la
búsqueda exhaustiva (sin límites) y comprobando que un `node_limit` produce un
estado **distinto** (`LIMIT_REACHED`), de modo que un FAILURE nunca se confunde
con «me quedé sin presupuesto».
"""

from __future__ import annotations

import time

from _harness import info, ok, solve, spec_of, title  # noqa: E402

from agent import SearchStatus  # noqa: E402

CIRCULAR = "caso4_dependencia_circular.json"
SIN_BATERIA = "caso4_bateria_insuficiente.json"

#: Tope de seguridad del propio test: si la búsqueda tardara más, es un fallo.
TIEMPO_MAXIMO_S = 60.0


def test_dependencia_circular_devuelve_failure() -> None:
    spec = spec_of(CIRCULAR)

    inicio = time.perf_counter()
    resultado = solve(spec)  # sin node_limit ni time_limit: búsqueda exacta
    transcurrido = time.perf_counter() - inicio

    assert resultado.status is SearchStatus.FAILURE
    assert resultado.solution_found is False
    assert resultado.plan == ()
    assert resultado.total_cost is None
    assert "OPEN" in resultado.message
    assert transcurrido < TIEMPO_MAXIMO_S

    info(f"status={resultado.status.value}  plan={resultado.plan}  total_cost={resultado.total_cost}")
    info(f"mensaje: {resultado.message}")
    info(f"{resultado.stats.describe()}")
    info(f"tiempo real del test: {transcurrido:.2f}s (tope {TIEMPO_MAXIMO_S:.0f}s)")
    ok("FAILURE devuelto por OPEN vacío, en tiempo acotado")


def test_la_busqueda_exploro_un_espacio_real() -> None:
    """Que no sea un FAILURE trivial: el mapa es transitable y se recorre entero."""

    spec = spec_of(CIRCULAR)
    resultado = solve(spec)

    assert resultado.stats.expanded > 100
    assert resultado.stats.generated > resultado.stats.expanded
    assert resultado.stats.closed_size > 100

    info(f"nodos expandidos={resultado.stats.expanded}  generados={resultado.stats.generated}")
    info(f"configuraciones físicas distintas en CLOSED={resultado.stats.closed_size}")
    ok("el FAILURE llega tras agotar un espacio de estados real, no un callejón inmediato")


def test_failure_no_se_confunde_con_limite_de_recursos() -> None:
    """Un tope de nodos produce LIMIT_REACHED, un estado distinto de FAILURE."""

    spec = spec_of(CIRCULAR)

    limitado = solve(spec, node_limit=50)
    exhaustivo = solve(spec)

    assert limitado.status is SearchStatus.LIMIT_REACHED
    assert limitado.solution_found is False
    assert exhaustivo.status is SearchStatus.FAILURE
    assert limitado.status is not exhaustivo.status

    info(f"con node_limit=50 : {limitado.status.value} — {limitado.message}")
    info(f"sin límites       : {exhaustivo.status.value} — {exhaustivo.message}")
    ok("el motor distingue «no hay solución» de «me corté por presupuesto»")


def test_bateria_insuficiente_devuelve_failure_inmediato() -> None:
    spec = spec_of(SIN_BATERIA)

    inicio = time.perf_counter()
    resultado = solve(spec, time_limit=TIEMPO_MAXIMO_S)
    transcurrido = time.perf_counter() - inicio

    assert resultado.status is SearchStatus.FAILURE
    assert resultado.plan == () and resultado.total_cost is None
    assert resultado.stats.generated == 0  # s₀ no tiene ni un sucesor
    assert transcurrido < 1.0

    info(f"status={resultado.status.value}  sucesores generados={resultado.stats.generated}")
    info(f"{resultado.stats.describe()}")
    ok("FAILURE inmediato cuando Applicable(s₀) es vacío")


def main() -> None:
    title(f"CASO 4 — Sin solución ({CIRCULAR} y {SIN_BATERIA})")
    test_dependencia_circular_devuelve_failure()
    test_la_busqueda_exploro_un_espacio_real()
    test_failure_no_se_confunde_con_limite_de_recursos()
    test_bateria_insuficiente_devuelve_failure_inmediato()


if __name__ == "__main__":
    main()
    print("\nCaso 4: OK")
