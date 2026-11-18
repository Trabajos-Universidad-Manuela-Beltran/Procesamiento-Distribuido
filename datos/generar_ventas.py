"""Genera un archivo CSV de ventas SINTÉTICAS (sin datos personales) y, aparte, la verdad calculada al generarlo.

La verdad (`ventas_N.verdad.json`) se acumula mientras se escribe cada fila, con código independiente del que se
usará para procesar, de modo que sirva para comprobar que el procesamiento secuencial, el paralelo y el
distribuido producen exactamente los mismos totales.

Uso: py datos/generar_ventas.py --n 500000 --salida datos/ventas_500k.csv [--semilla 42]
"""

import argparse
import json
import pathlib
import random
from datetime import date, timedelta

CIUDADES = {
    "Bogotá": 0.24,
    "Medellín": 0.14,
    "Cali": 0.12,
    "Barranquilla": 0.09,
    "Cartagena": 0.07,
    "Bucaramanga": 0.07,
    "Cúcuta": 0.06,
    "Pereira": 0.06,
    "Manizales": 0.05,
    "Santa Marta": 0.05,
    "Ibagué": 0.05,
}
PRODUCTOS = {  # nombre: precio base en pesos colombianos
    "Portátil 14 pulgadas": 2_850_000,
    "Portátil gamer": 4_900_000,
    "Teléfono gama media": 1_450_000,
    "Teléfono gama alta": 3_900_000,
    "Tableta 10 pulgadas": 1_150_000,
    "Monitor 24 pulgadas": 690_000,
    "Monitor 27 pulgadas": 990_000,
    "Teclado mecánico": 260_000,
    "Ratón inalámbrico": 85_000,
    "Auriculares con micrófono": 190_000,
    "Auriculares inalámbricos": 320_000,
    "Parlante portátil": 230_000,
    "Cámara web": 175_000,
    "Disco duro externo 1 TB": 290_000,
    "Memoria USB 64 GB": 38_000,
    "Memoria USB 128 GB": 62_000,
    "Tarjeta SD 128 GB": 70_000,
    "Cargador rápido": 75_000,
    "Cable USB-C": 28_000,
    "Batería externa": 140_000,
    "Router Wi-Fi 6": 310_000,
    "Repetidor Wi-Fi": 120_000,
    "Impresora multifuncional": 780_000,
    "Tinta de impresora": 95_000,
    "Silla ergonómica": 840_000,
    "Soporte para portátil": 110_000,
    "Base refrigerante": 98_000,
    "Smartwatch": 640_000,
    "Banda deportiva": 190_000,
    "Proyector portátil": 1_250_000,
}
# estacionalidad: mes -> peso (junio y diciembre concentran más compras)
MESES = {
    1: 0.85,
    2: 0.8,
    3: 0.9,
    4: 0.9,
    5: 1.0,
    6: 1.25,
    7: 1.0,
    8: 0.95,
    9: 0.95,
    10: 1.05,
    11: 1.35,
    12: 1.7,
}
ANIO = 2025
ENCABEZADO = "id_venta,fecha,ciudad,producto,cantidad,precio_unitario"


def _dias_ponderados() -> tuple[list[date], list[float]]:
    dias = [
        date(ANIO, 1, 1) + timedelta(days=i)
        for i in range((date(ANIO + 1, 1, 1) - date(ANIO, 1, 1)).days)
    ]
    return dias, [MESES[d.month] for d in dias]


def generar(n: int, salida: pathlib.Path, semilla: int = 42) -> dict:
    rng = random.Random(semilla)
    dias, pesos_dia = _dias_ponderados()
    ciudades, pesos_ciudad = list(CIUDADES), list(CIUDADES.values())
    productos = list(PRODUCTOS)
    pesos_producto = [
        1 / (1 + 0.012 * PRODUCTOS[p] / 10_000) for p in productos
    ]  # lo barato se vende más
    # elección por lotes para que generar 500.000 filas tarde segundos
    fechas = rng.choices(dias, weights=pesos_dia, k=n)
    ciudad_v = rng.choices(ciudades, weights=pesos_ciudad, k=n)
    producto_v = rng.choices(productos, weights=pesos_producto, k=n)
    verdad = {
        "filas": n,
        "semilla": semilla,
        "ingresos_por_ciudad": {},
        "cantidad_por_producto": {},
        "ingresos_por_mes": {},
    }
    por_ciudad, por_producto, por_mes = (
        verdad["ingresos_por_ciudad"],
        verdad["cantidad_por_producto"],
        verdad["ingresos_por_mes"],
    )
    salida.parent.mkdir(parents=True, exist_ok=True)
    with salida.open("w", encoding="utf-8", newline="\n") as f:
        f.write(ENCABEZADO + "\n")
        for i in range(n):
            producto, ciudad, fecha = producto_v[i], ciudad_v[i], fechas[i]
            cantidad = rng.choices((1, 2, 3, 4, 5), weights=(60, 22, 10, 5, 3))[0]
            precio = (
                round(PRODUCTOS[producto] * rng.uniform(0.92, 1.05) / 100) * 100
            )  # variaciones y descuentos, en pesos
            f.write(
                f"{i + 1},{fecha.isoformat()},{ciudad},{producto},{cantidad},{precio}\n"
            )
            por_ciudad[ciudad] = por_ciudad.get(ciudad, 0) + cantidad * precio
            por_producto[producto] = por_producto.get(producto, 0) + cantidad
            clave_mes = f"{fecha.month:02d}"
            por_mes[clave_mes] = por_mes.get(clave_mes, 0) + cantidad * precio
    destino = salida.with_suffix(".verdad.json")
    destino.write_text(
        json.dumps(verdad, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return verdad


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--salida", type=pathlib.Path, required=True)
    ap.add_argument("--semilla", type=int, default=42)
    a = ap.parse_args()
    v = generar(a.n, a.salida, a.semilla)
    print(
        f"{a.salida}: {v['filas']} filas, {a.salida.stat().st_size / 1e6:.1f} MB; ingresos totales {sum(v['ingresos_por_ciudad'].values()):,} COP".replace(
            ",", "."
        )
    )
