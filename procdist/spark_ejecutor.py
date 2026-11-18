"""Mismo cálculo con Apache Spark en modo local (un solo equipo, varios hilos): referencia de un motor distribuido real."""

import os
import time

from procdist.ejecutores import Resultado


def con_spark(ruta: str, hilos: int | str = "*", sesion=None) -> Resultado:
    """Calcula los tres indicadores con Spark. Si se pasa `sesion`, no se cuenta el arranque de la JVM."""
    from pyspark.sql import SparkSession, functions as F

    propia = sesion is None
    t0 = time.perf_counter()
    spark = (
        sesion
        or SparkSession.builder.master(f"local[{hilos}]")
        .appName("ventas")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "12")
        .getOrCreate()
    )
    ventas = (
        spark.read.option("header", True)
        .csv(ruta)
        .select(
            F.col("fecha").substr(6, 2).alias("mes"),
            "ciudad",
            "producto",
            F.col("cantidad").cast("long").alias("cantidad"),
            (
                F.col("cantidad").cast("long")
                * F.col("precio_unitario").cast("long")
            ).alias("ingreso"),
        )
    )
    ventas = ventas.cache()
    filas = ventas.count()
    por_ciudad = {
        r["ciudad"]: r["s"]
        for r in ventas.groupBy("ciudad").agg(F.sum("ingreso").alias("s")).collect()
    }
    por_producto = {
        r["producto"]: r["s"]
        for r in ventas.groupBy("producto")
        .agg(F.sum("cantidad").alias("s"))
        .collect()
    }
    por_mes = {
        r["mes"]: r["s"]
        for r in ventas.groupBy("mes").agg(F.sum("ingreso").alias("s")).collect()
    }
    total = time.perf_counter() - t0
    ventas.unpersist()  # libera la caché: una sesión reutilizada no acumula todos los conjuntos de datos
    if propia:
        spark.stop()
    top = sorted(por_producto.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    final = {
        "filas": filas,
        "ingresos_por_ciudad": dict(sorted(por_ciudad.items())),
        "cantidad_por_producto": dict(sorted(por_producto.items())),
        "ingresos_por_mes": dict(sorted(por_mes.items())),
        "top5_productos": top,
    }
    return Resultado(
        f"spark local[{hilos}]",
        final,
        total,
        procesos=(os.cpu_count() or 1) if hilos == "*" else int(hilos),
    )
