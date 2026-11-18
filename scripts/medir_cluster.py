"""Mide el clúster de contenedores (1, 2, 4 y 6 nodos) y la caída de un nodo; guarda evidencias/medicion_cluster.json.

Requiere `docker compose up -d --build` ejecutado antes. Uso: .venv\\Scripts\\python.exe scripts\\medir_cluster.py [--repeticiones 5]
"""

import argparse
import datetime
import json
import pathlib
import statistics
import subprocess
import sys
import time

import httpx

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "cluster"))
sys.stdout.reconfigure(encoding="utf-8")

from cluster.coordinador import ejecutar  # noqa: E402
from procdist.nucleo import coincide_con_verdad  # noqa: E402

TODOS = [f"http://127.0.0.1:{8000 + i}" for i in range(1, 7)]
NODOS_PRUEBA = (1, 2, 4, 6)


def esperar_nodos(urls: list[str], limite: float = 60.0) -> None:
    fin = time.time() + limite
    for u in urls:
        while True:
            try:
                if httpx.get(f"{u}/salud", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.time() > fin:
                raise TimeoutError(f"el nodo {u} no responde")
            time.sleep(0.5)


def levantar(servicios: list[str]) -> None:
    subprocess.run(
        ["docker", "compose", "up", "-d", *servicios],
        cwd=RAIZ,
        check=True,
        capture_output=True,
    )
    esperar_nodos(TODOS)


def verdad_de(archivo: str) -> dict:
    return json.loads(
        (RAIZ / "datos" / archivo)
        .with_suffix(".verdad.json")
        .read_text(encoding="utf-8")
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeticiones", type=int, default=5)
    ap.add_argument(
        "--archivos", nargs="+", default=["ventas_500k.csv", "ventas_2m.csv"]
    )
    a = ap.parse_args()
    esperar_nodos(TODOS)
    salida = {
        "fecha": datetime.datetime.now().isoformat(timespec="seconds"),
        "repeticiones": a.repeticiones,
        "escalado": [],
        "fallas": [],
    }
    for archivo in a.archivos:
        verdad = verdad_de(archivo)
        for n in NODOS_PRUEBA:
            nodos = TODOS[:n]
            ejecutar(nodos, archivo, 2 * n)  # calentamiento
            corridas = [
                ejecutar(nodos, archivo, 2 * n) for _ in range(a.repeticiones)
            ]
            assert all(
                coincide_con_verdad(c["resultado"], verdad) for c in corridas
            )
            tiempos = [c["segundos_total"] for c in corridas]
            salida["escalado"].append(
                {
                    "archivo": archivo,
                    "nodos": n,
                    "particiones": 2 * n,
                    "segundos": tiempos,
                    "mediana": statistics.median(tiempos),
                }
            )
            print(
                f"{archivo} {n} nodos: mediana {statistics.median(tiempos):.3f} s",
                flush=True,
            )
    archivo = "ventas_500k.csv"
    verdad = verdad_de(archivo)
    for nombre, reint in (("falla_con_reintento", 2), ("falla_sin_reintento", 0)):
        r = ejecutar(TODOS[:4], archivo, 8, falla_en=3, reintentos=reint)
        r["correcto"] = coincide_con_verdad(r["resultado"], verdad)
        r["escenario"] = nombre
        salida["fallas"].append(r)
        print(nombre, "correcto:", r["correcto"], r["eventos"], flush=True)
        levantar(
            [f"nodo{i}" for i in range(1, 7)]
        )  # el nodo caído se vuelve a iniciar
    destino = RAIZ / "evidencias" / "medicion_cluster.json"
    destino.write_text(
        json.dumps(salida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print("Guardado en", destino)
