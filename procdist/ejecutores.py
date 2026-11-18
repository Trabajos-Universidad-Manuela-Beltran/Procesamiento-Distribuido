"""Modos de ejecución: secuencial, paralelo (procesos independientes del mismo equipo) y paralelo con fallas y reintentos."""

import os
import time
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import dataclass, field

from procdist.nucleo import (
    Particion,
    Parcial,
    consolidar,
    particionar,
    procesar_particion,
)


@dataclass
class Resultado:
    """Resultado de una ejecución: indicadores consolidados, tiempos y bitácora de eventos."""

    modo: str
    resultado: dict
    segundos_total: float
    segundos_trabajo: list[float] = field(
        default_factory=list
    )  # tiempo de cada partición dentro de su proceso
    segundos_consolidacion: float = 0.0
    particiones: int = 1
    procesos: int = 1
    eventos: list[str] = field(default_factory=list)


def secuencial(ruta: str) -> Resultado:
    """Línea base: una sola partición que cubre todo el archivo, en un solo proceso."""
    t0 = time.perf_counter()
    parcial = procesar_particion(ruta, particionar(ruta, 1)[0])
    t1 = time.perf_counter()
    final = consolidar([parcial])
    return Resultado(
        "secuencial",
        final,
        time.perf_counter() - t0,
        [parcial.segundos],
        time.perf_counter() - t1,
    )


def _trabajo(
    ruta: str, particion: Particion, falla_en_intento_1: bool, intento: int
) -> Parcial:
    """Función que ejecuta cada proceso. Puede simular que el nodo cae antes de entregar su resultado."""
    if falla_en_intento_1 and intento == 1:
        raise RuntimeError(
            f"nodo caído simulado en la partición {particion.indice} (proceso {os.getpid()})"
        )
    return procesar_particion(ruta, particion)


def paralelo(
    ruta: str,
    procesos: int,
    particiones: int | None = None,
    falla_particion: int | None = None,
    reintentos: int = 2,
    pool: ProcessPoolExecutor | None = None,
) -> Resultado:
    """Reparte las particiones entre `procesos` procesos independientes y consolida los parciales.

    Si `falla_particion` indica una partición, su primer intento falla (nodo caído simulado). Con `reintentos` > 0 el coordinador
    reasigna la partición y el resultado sigue siendo correcto; con 0, la partición se pierde y se detecta por el conteo de filas.
    `pool` permite reutilizar un grupo de procesos ya creado (el arranque de los procesos no se cuenta en ese caso).
    """
    partes = particionar(ruta, particiones or procesos)
    n_part = len(partes)
    eventos: list[str] = []
    t0 = time.perf_counter()
    propio = pool is None
    ejecutor = pool or ProcessPoolExecutor(max_workers=procesos)
    parciales: list[Parcial] = []
    try:
        pendientes: dict[Future, tuple[Particion, int]] = {
            ejecutor.submit(_trabajo, ruta, p, p.indice == falla_particion, 1): (
                p,
                1,
            )
            for p in partes
        }
        while pendientes:
            terminados, _ = wait(pendientes, return_when=FIRST_COMPLETED)
            for terminado in terminados:
                particion, intento = pendientes.pop(terminado)
                try:
                    parciales.append(terminado.result())
                except RuntimeError as e:
                    eventos.append(
                        f"intento {intento} de la partición {particion.indice} falló: {e}"
                    )
                    if intento <= reintentos:
                        eventos.append(
                            f"el coordinador reasigna la partición {particion.indice} (intento {intento + 1})"
                        )
                        pendientes[
                            ejecutor.submit(
                                _trabajo, ruta, particion, False, intento + 1
                            )
                        ] = (particion, intento + 1)
                    else:
                        eventos.append(
                            f"la partición {particion.indice} se pierde: sin reintentos disponibles"
                        )
    finally:
        if propio:
            ejecutor.shutdown()
    t1 = time.perf_counter()
    final = consolidar(parciales)
    nombre = (
        "paralelo"
        if falla_particion is None
        else (
            "paralelo con falla y reintento"
            if reintentos
            else "paralelo con falla sin reintento"
        )
    )
    return Resultado(
        nombre,
        final,
        time.perf_counter() - t0,
        [p.segundos for p in parciales],
        time.perf_counter() - t1,
        n_part,
        procesos,
        eventos,
    )
