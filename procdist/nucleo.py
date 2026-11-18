"""Núcleo del procesamiento: partición del archivo por rangos de bytes, trabajo de cada nodo (map) y consolidación (reduce).

Es el mismo código para los tres modos: el secuencial procesa una sola partición que cubre todo el archivo, el paralelo
reparte particiones entre procesos del mismo equipo y el distribuido las reparte entre contenedores que se comunican por red.
"""

import os
import time
from collections import Counter
from dataclasses import dataclass, field

TOP = 5


@dataclass(frozen=True)
class Particion:
    """Rango de bytes [inicio, fin) de un archivo. Cada partición procesa las líneas que EMPIEZAN dentro del rango."""

    indice: int
    inicio: int
    fin: int


@dataclass
class Parcial:
    """Resultado parcial de una partición: se puede sumar con otros sin releer los datos."""

    indice: int
    filas: int = 0
    ingresos_ciudad: Counter = field(default_factory=Counter)
    cantidad_producto: Counter = field(default_factory=Counter)
    ingresos_mes: Counter = field(default_factory=Counter)
    segundos: float = 0.0
    pid: int = 0


def particionar(ruta: str, n: int) -> list[Particion]:
    """Divide el archivo en `n` rangos de bytes casi iguales (como los bloques de un sistema de archivos distribuido)."""
    if n < 1:
        raise ValueError("Debe haber al menos una partición")
    return particionar_tamano(os.path.getsize(ruta), n)


def particionar_tamano(tamano: int, n: int) -> list[Particion]:
    """Igual que `particionar`, pero a partir del tamaño en bytes (el coordinador del clúster no tiene el archivo)."""
    if n < 1:
        raise ValueError("Debe haber al menos una partición")
    n = max(1, min(n, tamano))  # no tiene sentido pedir más particiones que bytes
    base = tamano // n
    limites = [i * base for i in range(n)] + [tamano]
    return [Particion(i, limites[i], limites[i + 1]) for i in range(n)]


def procesar_particion(ruta: str, particion: Particion) -> Parcial:
    """Trabajo de un nodo (fase map): lee su rango y agrega ingresos por ciudad, cantidad por producto e ingresos por mes."""
    t0 = time.perf_counter()
    parcial = Parcial(indice=particion.indice, pid=os.getpid())
    ingresos_ciudad, cantidad_producto, ingresos_mes = (
        parcial.ingresos_ciudad,
        parcial.cantidad_producto,
        parcial.ingresos_mes,
    )
    filas = 0
    with open(ruta, "rb") as f:
        if particion.inicio == 0:
            f.readline()  # encabezado
        else:
            f.seek(particion.inicio - 1)
            f.readline()  # descarta el resto de la línea que cruza el límite: pertenece a la partición anterior
        while (
            f.tell() < particion.fin
        ):  # procesa las líneas que EMPIEZAN dentro de [inicio, fin)
            linea = f.readline()
            if not linea:
                break
            _, fecha, ciudad, producto, cantidad, precio = (
                linea.decode("utf-8").rstrip("\n").split(",")
            )
            ingreso = int(cantidad) * int(precio)
            ingresos_ciudad[ciudad] += ingreso
            cantidad_producto[producto] += int(cantidad)
            ingresos_mes[fecha[5:7]] += ingreso
            filas += 1
    parcial.filas = filas
    parcial.segundos = time.perf_counter() - t0
    return parcial


def consolidar(parciales: list[Parcial]) -> dict:
    """Fase reduce: suma los resultados parciales y obtiene los indicadores finales."""
    ciudad, producto, mes = Counter(), Counter(), Counter()
    filas = 0
    for p in parciales:
        ciudad.update(p.ingresos_ciudad)
        producto.update(p.cantidad_producto)
        mes.update(p.ingresos_mes)
        filas += p.filas
    return {
        "filas": filas,
        "ingresos_por_ciudad": dict(sorted(ciudad.items())),
        "cantidad_por_producto": dict(sorted(producto.items())),
        "ingresos_por_mes": dict(sorted(mes.items())),
        "top5_productos": producto.most_common(TOP),
    }


def coincide_con_verdad(resultado: dict, verdad: dict) -> bool:
    """Compara con la verdad calculada al generar los datos (código independiente)."""
    return (
        resultado["filas"] == verdad["filas"]
        and resultado["ingresos_por_ciudad"]
        == dict(sorted(verdad["ingresos_por_ciudad"].items()))
        and resultado["cantidad_por_producto"]
        == dict(sorted(verdad["cantidad_por_producto"].items()))
        and resultado["ingresos_por_mes"]
        == dict(sorted(verdad["ingresos_por_mes"].items()))
    )
