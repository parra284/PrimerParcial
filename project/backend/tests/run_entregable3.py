"""Ejecuta los cinco casos del Entregable 3 y resume el resultado.

    cd project/backend
    python tests/run_entregable3.py

Cada caso también se puede correr por separado::

    python tests/test_caso1_estados_equivalentes.py
"""

from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_caso1_estados_equivalentes as caso1  # noqa: E402
import test_caso2_informacion_relevante as caso2  # noqa: E402
import test_caso3_costos_vs_pasos as caso3  # noqa: E402
import test_caso4_sin_solucion as caso4  # noqa: E402
import test_caso5_rutas_alternativas as caso5  # noqa: E402

CASOS = [
    ("Caso 1 — Estados equivalentes", caso1),
    ("Caso 2 — Información relevante", caso2),
    ("Caso 3 — Costos diferentes", caso3),
    ("Caso 4 — Sin solución", caso4),
    ("Caso 5 — Rutas alternativas", caso5),
]


def main() -> int:
    resultados: list[tuple[str, bool, float, str]] = []

    for etiqueta, modulo in CASOS:
        inicio = time.perf_counter()
        try:
            modulo.main()
            resultados.append((etiqueta, True, time.perf_counter() - inicio, ""))
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            resultados.append((etiqueta, False, time.perf_counter() - inicio, str(exc)))

    print("\n" + "=" * 74)
    print("RESUMEN — ENTREGABLE 3")
    print("=" * 74)
    for etiqueta, paso, segundos, detalle in resultados:
        estado = "PASA" if paso else "FALLA"
        print(f"  {estado:<5} {etiqueta:<38} {segundos:>6.2f}s  {detalle}")

    fallidos = [r for r in resultados if not r[1]]
    total = sum(r[2] for r in resultados)
    print(f"\n  {len(resultados) - len(fallidos)}/{len(resultados)} casos pasan "
          f"({total:.2f}s en total)")
    return 1 if fallidos else 0


if __name__ == "__main__":
    raise SystemExit(main())
