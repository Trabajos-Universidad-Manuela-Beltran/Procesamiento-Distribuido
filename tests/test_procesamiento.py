"""Pruebas del núcleo y de los modos de ejecución: los resultados deben coincidir con la verdad calculada al generar los datos."""

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "datos"))

from generar_ventas import generar  # noqa: E402
from procdist.ejecutores import paralelo, secuencial  # noqa: E402
from procdist.nucleo import (
    coincide_con_verdad,
    consolidar,
    particionar,
    procesar_particion,
)  # noqa: E402


@pytest.fixture(scope="module")
def datos(tmp_path_factory):
    ruta = tmp_path_factory.mktemp("datos") / "ventas.csv"
    verdad = generar(3000, ruta, semilla=7)
    return str(ruta), verdad


def test_las_particiones_cubren_el_archivo_sin_huecos(datos):
    ruta, _ = datos
    partes = particionar(ruta, 7)
    assert (
        partes[0].inicio == 0
        and partes[-1].fin == pathlib.Path(ruta).stat().st_size
    )
    assert all(a.fin == b.inicio for a, b in zip(partes, partes[1:]))
    with pytest.raises(ValueError):
        particionar(ruta, 0)


@pytest.mark.parametrize("n", [1, 2, 3, 5, 8, 13, 64])
def test_ninguna_fila_se_pierde_ni_se_repite_con_cualquier_numero_de_particiones(
    datos, n
):
    ruta, verdad = datos
    parciales = [procesar_particion(ruta, p) for p in particionar(ruta, n)]
    assert sum(p.filas for p in parciales) == verdad["filas"]
    assert coincide_con_verdad(consolidar(parciales), verdad)


def test_secuencial_coincide_con_la_verdad(datos):
    ruta, verdad = datos
    r = secuencial(ruta)
    assert coincide_con_verdad(r.resultado, verdad)
    assert len(r.resultado["top5_productos"]) == 5


def test_paralelo_da_el_mismo_resultado_que_el_secuencial(datos):
    ruta, verdad = datos
    p = paralelo(ruta, procesos=3)
    assert (
        coincide_con_verdad(p.resultado, verdad)
        and p.resultado == secuencial(ruta).resultado
    )


def test_falla_con_reintento_sigue_siendo_correcta(datos):
    ruta, verdad = datos
    r = paralelo(ruta, procesos=3, particiones=6, falla_particion=2, reintentos=2)
    assert coincide_con_verdad(r.resultado, verdad)
    assert (
        any("reasigna" in e for e in r.eventos)
        and r.modo == "paralelo con falla y reintento"
    )


def test_falla_sin_reintento_se_detecta_porque_faltan_filas(datos):
    ruta, verdad = datos
    r = paralelo(ruta, procesos=3, particiones=6, falla_particion=2, reintentos=0)
    assert r.resultado["filas"] < verdad["filas"] and not coincide_con_verdad(
        r.resultado, verdad
    )
    assert any("se pierde" in e for e in r.eventos)


def test_la_verdad_guardada_se_puede_leer_de_disco(datos, tmp_path):
    ruta, verdad = datos
    guardada = json.loads(
        pathlib.Path(ruta).with_suffix(".verdad.json").read_text(encoding="utf-8")
    )
    assert guardada["filas"] == verdad["filas"] == 3000


def test_pedir_mas_particiones_que_bytes_no_genera_rangos_vacios(tmp_path):
    from procdist.nucleo import particionar_tamano

    partes = particionar_tamano(5, 50)
    assert len(partes) == 5 and all(p.fin > p.inicio for p in partes)
    assert sum(p.fin - p.inicio for p in partes) == 5
