"""Nodo trabajador: recibe por HTTP un rango de bytes de un archivo de ventas y devuelve el resultado parcial.

Cada contenedor ejecuta una instancia. Solo lee archivos del directorio de datos (por nombre, sin rutas).
"""

import os
import pathlib
import threading

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from procdist.nucleo import Particion, procesar_particion

DIRECTORIO_DATOS = pathlib.Path(os.environ.get("DIRECTORIO_DATOS", "/datos"))
NOMBRE_NODO = os.environ.get("NOMBRE_NODO", "trabajador")
# Solo para las pruebas de tolerancia a fallas.
PERMITIR_CAIDA_SIMULADA = os.environ.get("PERMITIR_CAIDA_SIMULADA") == "1"
# Tope razonable para un desplazamiento dentro de un archivo.
MAX_BYTES = 2**53

app = FastAPI(title=f"Nodo {NOMBRE_NODO}")
# Un nodo atiende una partición a la vez, como un núcleo dedicado.
_ocupado = threading.Lock()


class Tarea(BaseModel):
    archivo: str = Field(pattern=r"^[A-Za-z0-9_\-]+\.csv$")
    indice: int = Field(ge=0)
    inicio: int = Field(ge=0, le=MAX_BYTES)
    fin: int = Field(gt=0, le=MAX_BYTES)
    # El nodo "cae" sin responder; solo se acepta si el nodo lo permite (ver /procesar).
    simular_caida: bool = False


def _ruta(nombre: str) -> pathlib.Path:
    ruta = DIRECTORIO_DATOS / nombre
    if not ruta.is_file():
        raise HTTPException(
            status_code=404, detail=f"no existe {nombre} en el nodo"
        )
    return ruta


@app.get("/salud")
def salud() -> dict:
    return {"nodo": NOMBRE_NODO, "estado": "activo", "pid": os.getpid()}


@app.get("/tamano/{archivo}")
def tamano(archivo: str) -> dict:
    if (
        not archivo.endswith(".csv")
        or "/" in archivo
        or "\\" in archivo
        or ".." in archivo
    ):
        raise HTTPException(status_code=400, detail="nombre de archivo no válido")
    return {"archivo": archivo, "bytes": _ruta(archivo).stat().st_size}


@app.post("/procesar")
def procesar(tarea: Tarea) -> dict:
    if tarea.fin <= tarea.inicio:
        raise HTTPException(status_code=422, detail="el rango debe ser creciente")
    if tarea.simular_caida:
        if not PERMITIR_CAIDA_SIMULADA:
            raise HTTPException(
                status_code=403,
                detail="la caída simulada no está habilitada en este nodo",
            )
        # El proceso muere sin responder: el coordinador ve la conexión rota y reasigna.
        os._exit(1)
    ruta = _ruta(tarea.archivo)
    with _ocupado:
        parcial = procesar_particion(
            str(ruta), Particion(tarea.indice, tarea.inicio, tarea.fin)
        )
    return {
        "nodo": NOMBRE_NODO,
        "indice": parcial.indice,
        "filas": parcial.filas,
        "segundos": parcial.segundos,
        "ingresos_ciudad": dict(parcial.ingresos_ciudad),
        "cantidad_producto": dict(parcial.cantidad_producto),
        "ingresos_mes": dict(parcial.ingresos_mes),
    }
