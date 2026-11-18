"""Prueba de concurrencia y de tiempos de respuesta contra nodos reales (procesos uvicorn en localhost).

Envía muchas solicitudes a la vez y comprueba que ninguna mezcla resultados: la suma de filas y de ingresos de todas las
respuestas debe ser igual a la verdad. Guarda evidencias/concurrencia.json.

Uso: .venv\\Scripts\\python.exe scripts\\prueba_concurrencia.py [--archivo ventas_500k.csv]
"""

import argparse
import datetime
import json
import os
import pathlib
import socket
import statistics
import subprocess
import sys
import threading
import time

import httpx

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.stdout.reconfigure(encoding="utf-8")

from procdist.nucleo import particionar_tamano  # noqa: E402


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def iniciar_nodo(nombre: str) -> tuple[subprocess.Popen, str]:
    puerto = puerto_libre()
    entorno = {
        **os.environ,
        "DIRECTORIO_DATOS": str(RAIZ / "datos"),
        "NOMBRE_NODO": nombre,
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "cluster.trabajador:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(puerto),
            "--log-level",
            "warning",
        ],
        cwd=RAIZ,
        env=entorno,
    )
    url = f"http://127.0.0.1:{puerto}"
    limite = time.time() + 30
    while time.time() < limite:
        try:
            if httpx.get(f"{url}/salud", timeout=1).status_code == 200:
                return proc, url
        except httpx.HTTPError:
            time.sleep(0.2)
    proc.kill()
    raise TimeoutError(f"el nodo {nombre} no arrancó")


def percentil(valores: list[float], p: float) -> float:
    orden = sorted(valores)
    return orden[min(len(orden) - 1, int(p * len(orden)))]


def rafaga_procesar(urls: list[str], archivo: str, solicitudes: int) -> dict:
    """Todas las particiones del archivo se piden al mismo tiempo, repartidas entre los nodos por turnos."""
    tamano = httpx.get(f"{urls[0]}/tamano/{archivo}").json()["bytes"]
    partes = particionar_tamano(tamano, solicitudes)
    respuestas: list[dict] = [None] * len(partes)  # type: ignore[list-item]
    latencias: list[float] = [0.0] * len(partes)
    errores: list[str] = []

    def pedir(i: int) -> None:
        p = partes[i]
        cuerpo = {
            "archivo": archivo,
            "indice": p.indice,
            "inicio": p.inicio,
            "fin": p.fin,
        }
        t0 = time.perf_counter()
        try:
            r = httpx.post(
                f"{urls[i % len(urls)]}/procesar", json=cuerpo, timeout=300
            )
            r.raise_for_status()
            respuestas[i] = r.json()
        except httpx.HTTPError as e:
            errores.append(f"{type(e).__name__}: {e}")
        latencias[i] = time.perf_counter() - t0

    hilos = [threading.Thread(target=pedir, args=(i,)) for i in range(len(partes))]
    t0 = time.perf_counter()
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    total = time.perf_counter() - t0
    buenas = [r for r in respuestas if r]
    return {
        "nodos": len(urls),
        "solicitudes": solicitudes,
        "errores": errores,
        "segundos_total": total,
        "latencia_min": min(latencias),
        "latencia_mediana": statistics.median(latencias),
        "latencia_max": max(latencias),
        "filas": sum(r["filas"] for r in buenas),
        "ingreso": sum(sum(r["ingresos_ciudad"].values()) for r in buenas),
        "filas_por_segundo": sum(r["filas"] for r in buenas) / total,
    }


def rafaga_salud(url: str, solicitudes: int, hilos_simultaneos: int) -> dict:
    """Muchas consultas ligeras a /salud con varios hilos a la vez: mide el tiempo de respuesta sin carga de cálculo."""
    latencias: list[float] = []
    fallos = [0]
    cerrojo = threading.Lock()
    siguiente = [0]

    def trabajo() -> None:
        with httpx.Client(timeout=30) as c:
            while True:
                with cerrojo:
                    if siguiente[0] >= solicitudes:
                        return
                    siguiente[0] += 1
                t0 = time.perf_counter()
                try:
                    c.get(f"{url}/salud").raise_for_status()
                except httpx.HTTPError:
                    with cerrojo:
                        fallos[0] += 1
                    continue
                dt = time.perf_counter() - t0
                with cerrojo:
                    latencias.append(dt)

    hilos = [threading.Thread(target=trabajo) for _ in range(hilos_simultaneos)]
    t0 = time.perf_counter()
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    total = time.perf_counter() - t0
    return {
        "solicitudes": solicitudes,
        "hilos": hilos_simultaneos,
        "fallos": fallos[0],
        "segundos_total": total,
        "solicitudes_por_segundo": len(latencias) / total,
        "latencia_mediana_ms": 1000 * statistics.median(latencias),
        "latencia_p95_ms": 1000 * percentil(latencias, 0.95),
        "latencia_max_ms": 1000 * max(latencias),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archivo", default="ventas_500k.csv")
    a = ap.parse_args()
    verdad = json.loads(
        (RAIZ / "datos" / a.archivo)
        .with_suffix(".verdad.json")
        .read_text(encoding="utf-8")
    )
    ingreso_total = sum(verdad["ingresos_por_ciudad"].values())
    nodos = [iniciar_nodo(f"nodo{i}") for i in range(1, 5)]
    urls = [u for _, u in nodos]
    salida: dict = {
        "fecha": datetime.datetime.now().isoformat(timespec="seconds"),
        "archivo": a.archivo,
        "filas_esperadas": verdad["filas"],
        "ingreso_esperado": ingreso_total,
        "procesar": [],
    }
    try:
        for u in urls:  # calentamiento de cada nodo
            httpx.get(f"{u}/salud")
        for cantidad_nodos, solicitudes in (
            (1, 8),
            (1, 32),
            (4, 8),
            (4, 32),
            (4, 64),
        ):
            r = rafaga_procesar(urls[:cantidad_nodos], a.archivo, solicitudes)
            r["correcto"] = (
                not r["errores"]
                and r["filas"] == verdad["filas"]
                and r["ingreso"] == ingreso_total
            )
            salida["procesar"].append(r)
            filas_s = f"{r['filas_por_segundo']:,.0f}".replace(",", ".")
            print(
                f"{cantidad_nodos} nodo(s), {solicitudes} solicitudes a la vez: "
                f"{r['segundos_total']:.2f} s, latencia mediana {r['latencia_mediana']:.2f} s, "
                f"máxima {r['latencia_max']:.2f} s, {filas_s} filas/s, "
                f"correcto={r['correcto']}",
                flush=True,
            )
        salida["salud"] = []
        for hilos in (1, 10, 50):
            r = rafaga_salud(urls[0], 500, hilos)
            salida["salud"].append(r)
            print(
                f"/salud, {hilos} hilos: {r['solicitudes_por_segundo']:.0f} solicitudes/s, "
                f"mediana {r['latencia_mediana_ms']:.1f} ms, p95 {r['latencia_p95_ms']:.1f} ms, "
                f"fallos {r['fallos']}",
                flush=True,
            )
    finally:
        for proc, _ in nodos:
            proc.kill()
            proc.wait(timeout=10)
    destino = RAIZ / "evidencias" / "concurrencia.json"
    destino.write_text(
        json.dumps(salida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print("Guardado en", destino.relative_to(RAIZ))
    return 0 if all(r["correcto"] for r in salida["procesar"]) else 1


if __name__ == "__main__":
    sys.exit(main())

