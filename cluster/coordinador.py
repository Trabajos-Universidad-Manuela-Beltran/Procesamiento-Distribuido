"""Coordinador del clúster: reparte particiones entre los nodos por HTTP, reasigna si un nodo falla y consolida.

Uso: py cluster/coordinador.py --archivo ventas_500k.csv --nodos http://localhost:8001 http://localhost:8002 [--particiones 8]
                              [--falla-en 3] [--sin-reintento] [--salida evidencias/cluster.json]

Dos tipos de error se tratan distinto:
  * Error de transporte (conexión rota, tiempo agotado): se asume que el nodo cayó; se retira y la partición se reasigna.
  * Error de la aplicación (HTTP 4xx/5xx o respuesta inválida): se repetiría igual en cualquier nodo; la partición se da por
    perdida y el nodo sigue activo, para que un dato malo no tumbe todo el clúster.
"""

import argparse
import json
import pathlib
import queue
import sys
import threading
import time
from collections import Counter

import httpx

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from procdist.nucleo import (
    Parcial,
    Particion,
    coincide_con_verdad,
    consolidar,
    particionar_tamano,
)  # noqa: E402

TIEMPO_MAXIMO = 120.0


def _a_parcial(r: dict) -> Parcial:
    return Parcial(
        indice=r["indice"],
        filas=r["filas"],
        ingresos_ciudad=Counter(r["ingresos_ciudad"]),
        cantidad_producto=Counter(r["cantidad_producto"]),
        ingresos_mes=Counter(r["ingresos_mes"]),
        segundos=r["segundos"],
    )


def _tamano_archivo(nodos: list[str], archivo: str) -> int:
    """Pide el tamaño al primer nodo que responda (el coordinador no tiene el archivo)."""
    with httpx.Client(timeout=TIEMPO_MAXIMO) as c:
        for url in nodos:
            try:
                return (
                    c.get(f"{url}/tamano/{archivo}")
                    .raise_for_status()
                    .json()["bytes"]
                )
            except httpx.TransportError:
                continue
    raise RuntimeError("ningún nodo responde")


def ejecutar(
    nodos: list[str],
    archivo: str,
    n_part: int,
    falla_en: int | None = None,
    reintentos: int = 2,
) -> dict:
    """Reparte `n_part` particiones entre `nodos`. Un nodo toma una tarea a la vez (cola compartida)."""
    if n_part < 1 or not nodos:
        raise ValueError("Se necesita al menos un nodo y una partición")
    partes = particionar_tamano(_tamano_archivo(nodos, archivo), n_part)
    cola: queue.Queue = queue.Queue()
    for p in partes:
        cola.put((p, 1))
    parciales: list[Parcial] = []
    eventos: list[str] = []
    perdidas: list[int] = []
    cerrojo = threading.Lock()
    caidos: set[str] = set()
    pendientes = {"n": len(partes)}

    def perder(p: Particion, motivo: str) -> None:
        with cerrojo:
            eventos.extend([motivo, f"la partición {p.indice} se pierde"])
            perdidas.append(p.indice)
            pendientes["n"] -= 1

    def nodo_cayo(url: str, p: Particion, intento: int, error: Exception) -> None:
        with cerrojo:
            caidos.add(url)
            eventos.append(
                f"el nodo {url} no respondió en la partición {p.indice} (intento {intento}): {type(error).__name__}"
            )
            reasignar = intento <= reintentos
            if reasignar:
                eventos.append(
                    f"el coordinador reasigna la partición {p.indice} a otro nodo (intento {intento + 1})"
                )
                cola.put((p, intento + 1))
        if not reasignar:
            perder(p, f"la partición {p.indice} no tiene reintentos disponibles")

    def nodo_trabaja(url: str) -> None:
        with httpx.Client(timeout=TIEMPO_MAXIMO) as cliente:
            while url not in caidos:
                try:
                    p, intento = cola.get(timeout=0.2)
                except queue.Empty:
                    with cerrojo:
                        if pendientes["n"] == 0:
                            return
                    continue
                cuerpo = {
                    "archivo": archivo,
                    "indice": p.indice,
                    "inicio": p.inicio,
                    "fin": p.fin,
                    "simular_caida": falla_en == p.indice and intento == 1,
                }
                try:
                    r = cliente.post(f"{url}/procesar", json=cuerpo)
                    r.raise_for_status()
                    parcial = _a_parcial(r.json())
                except httpx.HTTPStatusError as e:
                    perder(
                        p,
                        f"el nodo {url} rechazó la partición {p.indice} con HTTP {e.response.status_code}",
                    )
                except (ValueError, KeyError) as e:
                    perder(
                        p,
                        f"respuesta no válida del nodo {url} para la partición {p.indice}: {type(e).__name__}",
                    )
                except httpx.TransportError as e:
                    nodo_cayo(url, p, intento, e)
                    return
                else:
                    with cerrojo:
                        parciales.append(parcial)
                        pendientes["n"] -= 1

    t0 = time.perf_counter()
    hilos = [threading.Thread(target=nodo_trabaja, args=(u,)) for u in nodos]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    t1 = time.perf_counter()
    while (
        not cola.empty()
    ):  # si cayeron todos los nodos, lo que queda en la cola no se pierde en silencio
        p, _ = cola.get_nowait()
        perdidas.append(p.indice)
        eventos.append(
            f"la partición {p.indice} se pierde: no quedan nodos activos"
        )
    final = consolidar(parciales)
    return {
        "nodos": len(nodos),
        "particiones": len(partes),
        "archivo": archivo,
        "segundos_total": time.perf_counter() - t0,
        "segundos_hasta_parciales": t1 - t0,
        "segundos_trabajo": sorted(p.segundos for p in parciales),
        "nodos_caidos": sorted(caidos),
        "particiones_perdidas": sorted(perdidas),
        "eventos": eventos,
        "resultado": final,
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--archivo", required=True)
    ap.add_argument("--nodos", nargs="+", required=True)
    ap.add_argument("--particiones", type=int)
    ap.add_argument("--falla-en", type=int)
    ap.add_argument("--sin-reintento", action="store_true")
    ap.add_argument("--salida", type=pathlib.Path)
    a = ap.parse_args()
    res = ejecutar(
        a.nodos,
        a.archivo,
        a.particiones if a.particiones is not None else len(a.nodos),
        a.falla_en,
        0 if a.sin_reintento else 2,
    )
    verdad = json.loads(
        (RAIZ / "datos" / a.archivo)
        .with_suffix(".verdad.json")
        .read_text(encoding="utf-8")
    )
    res["correcto"] = coincide_con_verdad(res["resultado"], verdad)
    print(
        f"{res['nodos']} nodos, {res['particiones']} particiones: {res['segundos_total']:.3f} s, correcto={res['correcto']}"
    )
    for e in res["eventos"]:
        print("  ", e)
    if a.salida:
        a.salida.write_text(
            json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
