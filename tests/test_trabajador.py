"""Pruebas del nodo trabajador (sin red ni Docker, con el cliente de pruebas de FastAPI)."""

import importlib
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "datos"))

from fastapi.testclient import TestClient  # noqa: E402

from generar_ventas import generar  # noqa: E402


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    generar(2000, tmp_path / "ventas_2k.csv", semilla=3)
    monkeypatch.setenv("DIRECTORIO_DATOS", str(tmp_path))
    sys.modules.pop("cluster.trabajador", None)
    trabajador = importlib.import_module(
        "cluster.trabajador"
    )  # se vuelve a importar para leer el directorio de pruebas
    return TestClient(trabajador.app), (tmp_path / "ventas_2k.csv").stat().st_size


def test_el_nodo_responde_su_estado(cliente):
    c, _ = cliente
    assert c.get("/salud").json()["estado"] == "activo"


def test_devuelve_el_tamano_del_archivo(cliente):
    c, tamano = cliente
    assert c.get("/tamano/ventas_2k.csv").json()["bytes"] == tamano


def test_procesa_un_rango_y_suma_las_filas_de_todas_las_particiones(cliente):
    c, tamano = cliente
    mitad = tamano // 2
    filas = 0
    for i, (ini, fin) in enumerate(((0, mitad), (mitad, tamano))):
        r = c.post(
            "/procesar",
            json={
                "archivo": "ventas_2k.csv",
                "indice": i,
                "inicio": ini,
                "fin": fin,
            },
        )
        assert r.status_code == 200
        filas += r.json()["filas"]
    assert filas == 2000


@pytest.mark.parametrize(
    "nombre", ["../secreto.csv", "..\\secreto.csv", "datos.txt", "a/b.csv"]
)
def test_rechaza_nombres_de_archivo_con_rutas_o_extensiones_raras(cliente, nombre):
    c, _ = cliente
    r = c.post(
        "/procesar", json={"archivo": nombre, "indice": 0, "inicio": 0, "fin": 10}
    )
    assert r.status_code == 422
    assert c.get(f"/tamano/{nombre}").status_code in (400, 404)


def test_archivo_inexistente_da_404_y_rango_invertido_da_422(cliente):
    c, _ = cliente
    assert (
        c.post(
            "/procesar",
            json={"archivo": "no_existe.csv", "indice": 0, "inicio": 0, "fin": 10},
        ).status_code
        == 404
    )
    assert (
        c.post(
            "/procesar",
            json={"archivo": "ventas_2k.csv", "indice": 0, "inicio": 50, "fin": 10},
        ).status_code
        == 422
    )


def test_la_caida_simulada_se_rechaza_si_el_nodo_no_la_habilita(cliente):
    c, _ = (
        cliente  # el cliente de pruebas no habilita PERMITIR_CAIDA_SIMULADA: si se aceptara, el nodo mataría a pytest
    )
    r = c.post(
        "/procesar",
        json={
            "archivo": "ventas_2k.csv",
            "indice": 0,
            "inicio": 0,
            "fin": 100,
            "simular_caida": True,
        },
    )
    assert r.status_code == 403


def test_rechaza_desplazamientos_enormes(cliente):
    c, _ = cliente
    r = c.post(
        "/procesar",
        json={"archivo": "ventas_2k.csv", "indice": 0, "inicio": 0, "fin": 10**30},
    )
    assert r.status_code == 422
