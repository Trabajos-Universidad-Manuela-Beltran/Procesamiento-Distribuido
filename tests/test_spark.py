"""Prueba del ejecutor de Spark local (lenta: arranca una JVM)."""

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "datos"))

pytest.importorskip("pyspark")

from generar_ventas import generar  # noqa: E402
from procdist.nucleo import coincide_con_verdad  # noqa: E402
from procdist.spark_ejecutor import con_spark  # noqa: E402


def test_spark_local_calcula_lo_mismo_que_la_verdad(tmp_path):
    ruta = tmp_path / "ventas_3k.csv"
    verdad = generar(3000, ruta, semilla=5)
    r = con_spark(str(ruta), hilos=2)
    assert coincide_con_verdad(r.resultado, verdad)
    assert len(r.resultado["top5_productos"]) == 5
