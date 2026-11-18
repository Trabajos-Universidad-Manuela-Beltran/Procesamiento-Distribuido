"""Mide secuencial vs paralelo (y Spark local) con varios tamaños y repeticiones; guarda evidencias/medicion_local.json.

Uso: .venv\\Scripts\\python.exe scripts\\medir_local.py [--repeticiones 5] [--tamanos 10k 100k 500k] [--spark]
"""

import argparse
import ctypes
import datetime
import json
import os
import pathlib
import platform
import statistics
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.stdout.reconfigure(encoding="utf-8")

from procdist.ejecutores import paralelo, secuencial  # noqa: E402
from procdist.nucleo import coincide_con_verdad  # noqa: E402

PROCESOS = (2, 4, 6, 12)


def hardware() -> dict:
    """Datos del equipo donde se midió."""

    class Mem(ctypes.Structure):
        _fields_ = [
            ("largo", ctypes.c_ulong),
            ("uso", ctypes.c_ulong),
            ("total", ctypes.c_ulonglong),
            ("libre", ctypes.c_ulonglong),
            ("pag_total", ctypes.c_ulonglong),
            ("pag_libre", ctypes.c_ulonglong),
            ("virt_total", ctypes.c_ulonglong),
            ("virt_libre", ctypes.c_ulonglong),
            ("ext", ctypes.c_ulonglong),
        ]

    mem = Mem()
    mem.largo = ctypes.sizeof(Mem)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
    try:
        cpu = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor).Name",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
        nucleos = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor).NumberOfCores",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        cpu, nucleos = platform.processor(), ""
    return {
        "cpu": cpu,
        "nucleos_fisicos": nucleos,
        "procesadores_logicos": os.cpu_count(),
        "ram_gib": round(mem.total / 2**30, 1),
        "sistema": f"{platform.system()} {platform.release()} ({platform.version()})",
        "python": platform.python_version(),
    }


def mediana(valores: list[float]) -> float:
    return statistics.median(valores)


def medir_tamano(
    ruta: pathlib.Path, repeticiones: int, con_spark: bool, sesion_spark
) -> dict:
    verdad = json.loads(
        ruta.with_suffix(".verdad.json").read_text(encoding="utf-8")
    )
    salida = {
        "archivo": ruta.name,
        "filas": verdad["filas"],
        "mb": round(ruta.stat().st_size / 1e6, 1),
    }
    tiempos = [secuencial(str(ruta)) for _ in range(repeticiones)]
    assert all(coincide_con_verdad(r.resultado, verdad) for r in tiempos)
    salida["secuencial"] = {
        "segundos": [r.segundos_total for r in tiempos],
        "mediana": mediana([r.segundos_total for r in tiempos]),
    }
    salida["paralelo_con_arranque"], salida["paralelo_pool_caliente"] = {}, {}
    for p in PROCESOS:
        frios = [paralelo(str(ruta), p) for _ in range(repeticiones)]
        assert all(coincide_con_verdad(r.resultado, verdad) for r in frios)
        salida["paralelo_con_arranque"][p] = {
            "segundos": [r.segundos_total for r in frios],
            "mediana": mediana([r.segundos_total for r in frios]),
        }
        with ProcessPoolExecutor(max_workers=p) as pool:
            paralelo(
                str(ruta), p, pool=pool
            )  # calentamiento: los procesos ya existen
            calientes = [
                paralelo(str(ruta), p, pool=pool) for _ in range(repeticiones)
            ]
        assert all(coincide_con_verdad(r.resultado, verdad) for r in calientes)
        salida["paralelo_pool_caliente"][p] = {
            "segundos": [r.segundos_total for r in calientes],
            "mediana": mediana([r.segundos_total for r in calientes]),
        }
        print(
            f"  {ruta.name} p={p}: arranque {salida['paralelo_con_arranque'][p]['mediana']:.3f} s, caliente "
            f"{salida['paralelo_pool_caliente'][p]['mediana']:.3f} s",
            flush=True,
        )
    if con_spark:
        from procdist.spark_ejecutor import con_spark as spark_calcular

        sp = [
            spark_calcular(str(ruta), sesion=sesion_spark)
            for _ in range(max(3, repeticiones // 2))
        ]
        assert all(coincide_con_verdad(r.resultado, verdad) for r in sp)
        salida["spark_local"] = {
            "segundos": [r.segundos_total for r in sp],
            "mediana": mediana([r.segundos_total for r in sp]),
        }
        print(
            f"  {ruta.name} spark: {salida['spark_local']['mediana']:.3f} s",
            flush=True,
        )
    s = salida["secuencial"]["mediana"]
    print(f"  {ruta.name} secuencial: {s:.3f} s", flush=True)
    return salida


def medir_fallas(ruta: pathlib.Path) -> dict:
    """Falla de una partición: con reintento el resultado es correcto; sin reintento faltan filas y se detecta."""
    verdad = json.loads(
        ruta.with_suffix(".verdad.json").read_text(encoding="utf-8")
    )
    res = {}
    for nombre, reint in (
        ("sin_falla", None),
        ("falla_con_reintento", 2),
        ("falla_sin_reintento", 0),
    ):
        r = (
            paralelo(str(ruta), 4, particiones=8)
            if reint is None
            else paralelo(
                str(ruta), 4, particiones=8, falla_particion=3, reintentos=reint
            )
        )
        res[nombre] = {
            "modo": r.modo,
            "segundos": r.segundos_total,
            "filas_obtenidas": r.resultado["filas"],
            "filas_esperadas": verdad["filas"],
            "correcto": coincide_con_verdad(r.resultado, verdad),
            "eventos": r.eventos,
        }
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeticiones", type=int, default=5)
    ap.add_argument("--tamanos", nargs="+", default=["10k", "100k", "500k"])
    ap.add_argument("--spark", action="store_true")
    ap.add_argument("--salida", default="medicion_local.json")
    a = ap.parse_args()
    sesion = None
    if a.spark:
        from pyspark.sql import SparkSession

        sesion = (
            SparkSession.builder.master("local[*]")
            .appName("ventas")
            .config("spark.ui.enabled", "false")
            .config("spark.sql.shuffle.partitions", "12")
            .getOrCreate()
        )
        sesion.sparkContext.setLogLevel("ERROR")
    resultado = {
        "fecha": datetime.datetime.now().isoformat(timespec="seconds"),
        "hardware": hardware(),
        "repeticiones": a.repeticiones,
        "tamanos": [],
    }
    print(resultado["hardware"], flush=True)
    for t in a.tamanos:
        print(f"Tamaño {t}", flush=True)
        resultado["tamanos"].append(
            medir_tamano(
                RAIZ / "datos" / f"ventas_{t}.csv", a.repeticiones, a.spark, sesion
            )
        )
    resultado["fallas"] = medir_fallas(RAIZ / "datos" / "ventas_500k.csv")
    if sesion:
        sesion.stop()
    destino = RAIZ / "evidencias" / a.salida
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print("Guardado en", destino)
