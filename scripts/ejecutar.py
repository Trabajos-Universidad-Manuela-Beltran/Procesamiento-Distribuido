"""Ejecuta el procesamiento sobre un CSV y muestra indicadores, parciales por partición, consolidación y tiempos.

Uso: .venv\\Scripts\\python.exe scripts\\ejecutar.py --archivo datos\\ventas_100k.csv [--procesos 4] [--falla-en 2] [--sin-reintento]
"""

import argparse
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.stdout.reconfigure(encoding="utf-8")

from procdist.ejecutores import paralelo, secuencial  # noqa: E402
from procdist.nucleo import (
    coincide_con_verdad,
    particionar,
    procesar_particion,
)  # noqa: E402


def miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def imprimir_indicadores(r: dict) -> None:
    print("\nIngresos por ciudad (COP):")
    for ciudad, valor in sorted(
        r["ingresos_por_ciudad"].items(), key=lambda kv: -kv[1]
    ):
        print(f"  {ciudad:<14}{miles(valor):>20}")
    print("\nTop 5 de productos por cantidad vendida:")
    for i, (producto, cantidad) in enumerate(r["top5_productos"], 1):
        print(f"  {i}. {producto:<28}{miles(cantidad):>10} unidades")
    print("\nIngresos por mes (COP):")
    for mes, valor in sorted(r["ingresos_por_mes"].items()):
        print(f"  {mes}{miles(valor):>22}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archivo", type=pathlib.Path, required=True)
    ap.add_argument("--procesos", type=int, default=4)
    ap.add_argument("--falla-en", type=int)
    ap.add_argument("--sin-reintento", action="store_true")
    a = ap.parse_args()
    ruta = str(a.archivo)
    verdad = json.loads(
        a.archivo.with_suffix(".verdad.json").read_text(encoding="utf-8")
    )

    print(
        f"Archivo: {a.archivo.name} ({miles(verdad['filas'])} filas, {a.archivo.stat().st_size / 1e6:.1f} MB)"
    )
    seq = secuencial(ruta)
    print(
        f"\n[secuencial] {seq.segundos_total:.3f} s, filas {miles(seq.resultado['filas'])}, coincide con la verdad: {coincide_con_verdad(seq.resultado, verdad)}"
    )

    print(f"\nResultados parciales con {a.procesos} particiones (fase map):")
    print(
        f"  {'partición':<10}{'rango de bytes':<26}{'filas':>10}{'ingresos (COP)':>22}"
    )
    for p in particionar(ruta, a.procesos):
        parcial = procesar_particion(ruta, p)
        print(
            f"  {p.indice:<10}{miles(p.inicio) + ' - ' + miles(p.fin):<26}{miles(parcial.filas):>10}{miles(sum(parcial.ingresos_ciudad.values())):>22}"
        )

    par = paralelo(
        ruta,
        a.procesos,
        falla_particion=a.falla_en,
        reintentos=0 if a.sin_reintento else 2,
    )
    suma_total = sum(par.resultado["ingresos_por_ciudad"].values())
    print(
        f"\nConsolidación (fase reduce): {miles(par.resultado['filas'])} filas, ingresos {miles(suma_total)} COP"
    )
    print(
        f"  verdad del generador:      {miles(verdad['filas'])} filas, ingresos {miles(sum(verdad['ingresos_por_ciudad'].values()))} COP"
    )
    print(
        f"\n[{par.modo}] {par.segundos_total:.3f} s con {par.procesos} procesos y {par.particiones} particiones, "
        f"coincide con la verdad: {coincide_con_verdad(par.resultado, verdad)}"
    )
    for e in par.eventos:
        print("  evento:", e)
    print(
        f"  aceleración Ts/Tp = {seq.segundos_total / par.segundos_total:.2f} (incluye el arranque de los procesos)"
    )
    imprimir_indicadores(par.resultado)
    return 0


if __name__ == "__main__":
    sys.exit(main())
