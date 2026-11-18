"""Pruebas de integración del coordinador con nodos reales (procesos uvicorn en localhost, sin Docker)."""

import os
import pathlib
import socket
import subprocess
import sys
import time

import httpx
import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "datos"))

from cluster.coordinador import ejecutar  # noqa: E402
from generar_ventas import generar  # noqa: E402
from procdist.nucleo import coincide_con_verdad  # noqa: E402

N_NODOS = 3


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _iniciar_nodo(
    directorio: pathlib.Path, nombre: str
) -> tuple[subprocess.Popen, str]:
    puerto = _puerto_libre()
    entorno = {
        **os.environ,
        "DIRECTORIO_DATOS": str(directorio),
        "NOMBRE_NODO": nombre,
        "PERMITIR_CAIDA_SIMULADA": "1",
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


@pytest.fixture()
def clusterito(tmp_path):
    verdad = generar(4000, tmp_path / "ventas_4k.csv", semilla=11)
    nodos = [_iniciar_nodo(tmp_path, f"nodo{i}") for i in range(1, N_NODOS + 1)]
    yield [u for _, u in nodos], verdad
    for proc, _ in nodos:
        proc.kill()
        proc.wait(timeout=10)


def test_el_coordinador_reparte_y_consolida_con_el_mismo_resultado_que_la_verdad(
    clusterito,
):
    urls, verdad = clusterito
    r = ejecutar(urls, "ventas_4k.csv", 6)
    assert coincide_con_verdad(r["resultado"], verdad)
    assert r["nodos_caidos"] == [] and r["particiones_perdidas"] == []


def test_si_un_nodo_cae_el_coordinador_reasigna_y_el_resultado_sigue_correcto(
    clusterito,
):
    urls, verdad = clusterito
    r = ejecutar(urls, "ventas_4k.csv", 6, falla_en=2, reintentos=2)
    assert coincide_con_verdad(r["resultado"], verdad)
    assert len(r["nodos_caidos"]) == 1 and any(
        "reasigna" in e for e in r["eventos"]
    )


def test_sin_reintentos_la_particion_se_pierde_y_la_comprobacion_lo_detecta(
    clusterito,
):
    urls, verdad = clusterito
    r = ejecutar(urls, "ventas_4k.csv", 6, falla_en=2, reintentos=0)
    assert r["particiones_perdidas"] == [2]
    assert r["resultado"]["filas"] < verdad["filas"] and not coincide_con_verdad(
        r["resultado"], verdad
    )


def test_un_solo_nodo_que_cae_deja_las_particiones_pendientes_como_perdidas_y_lo_informa(
    clusterito,
):
    urls, verdad = clusterito
    r = ejecutar(urls[:1], "ventas_4k.csv", 4, falla_en=0, reintentos=2)
    assert sorted(r["particiones_perdidas"]) == [0, 1, 2, 3]
    assert any("no quedan nodos activos" in e for e in r["eventos"])
    assert not coincide_con_verdad(r["resultado"], verdad)


def test_un_dato_malo_pierde_su_particion_pero_no_marca_nodos_como_caidos(
    clusterito, tmp_path
):
    urls, _ = clusterito
    lineas = (tmp_path / "ventas_4k.csv").read_text(encoding="utf-8").splitlines()
    lineas.insert(
        len(lineas) // 2, ""
    )  # línea vacía: el nodo responde 500 siempre, en cualquier nodo
    (tmp_path / "ventas_mala.csv").write_text(
        "\n".join(lineas) + "\n", encoding="utf-8"
    )
    r = ejecutar(urls, "ventas_mala.csv", 6)
    assert len(r["particiones_perdidas"]) == 1 and r["nodos_caidos"] == []
    assert any("HTTP 500" in e for e in r["eventos"])


def test_pedir_cero_particiones_o_cero_nodos_es_un_error_claro(clusterito):
    urls, _ = clusterito
    with pytest.raises(ValueError):
        ejecutar(urls, "ventas_4k.csv", 0)
    with pytest.raises(ValueError):
        ejecutar([], "ventas_4k.csv", 3)


def test_un_archivo_que_no_existe_falla_con_404(clusterito):
    urls, _ = clusterito
    with pytest.raises(httpx.HTTPStatusError):
        ejecutar(urls, "no_existe.csv", 3)
