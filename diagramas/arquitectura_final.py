"""Diagrama de arquitectura del proyecto final: cliente, coordinador, nodos, almacenamiento y mecanismos de comunicación (PNG).

Uso: .venv\\Scripts\\python.exe diagramas\\arquitectura_final.py
"""

import pathlib
import sys

sys.path.insert(
    0,
    "C:/Users/cuent/Documents/Universidad/Katherin/2026-02/Sistemas Transaccionales/herramientas_doc/build",
)
from dibujo import (  # noqa: E402
    AZUL,
    BLANCO,
    CLARO,
    CLARO2,
    ESCALA,
    GRIS_O,
    NEGRO,
    Lienzo,
    unitario,
)

W, H = 1300, 1060
c = Lienzo(W, H)


def banda(y0, y1, titulo):
    c.rect(40, y0, 1260, y1, relleno=(250, 251, 253), borde=AZUL, grosor=3)
    c.rect(40, y0, 1260, y0 + 46, relleno=AZUL, borde=AZUL, grosor=3)
    c.texto(650, y0 + 23, titulo, "b", 23, BLANCO, "mm")


def caja(x0, y0, x1, y1, titulo, sub="", relleno=CLARO, borde=AZUL, guiones=False):
    if guiones:
        c.rect(x0, y0, x1, y1, relleno=BLANCO, borde=BLANCO, grosor=1, radio=8)
        for lado in (
            ((x0, y0), (x1, y0)),
            ((x1, y0), (x1, y1)),
            ((x1, y1), (x0, y1)),
            ((x0, y1), (x0, y0)),
        ):
            c.linea(list(lado), borde, 2.5, guiones=True, patron=(9, 6))
    else:
        c.rect(x0, y0, x1, y1, relleno=relleno, borde=borde, grosor=2.5, radio=8)
    if sub:
        c.texto((x0 + x1) / 2, y0 + (y1 - y0) * 0.27, titulo, "b", 21, NEGRO, "mm")
        c.texto_caja(
            x0,
            y0 + (y1 - y0) * 0.45,
            x1,
            y1,
            sub,
            "n",
            18,
            GRIS_O,
            interlinea=1.2,
            margen=10,
            valign="t",
        )
    else:
        c.texto_caja(x0, y0, x1, y1, titulo, "b", 21, NEGRO)


def flecha(pts, doble=False, color=NEGRO, grosor=3):
    c.linea(pts, color, grosor)
    c.punta_abierta(pts[-1], unitario(pts[-2], pts[-1]), color, grosor, 20, 10)
    if doble:
        c.punta_abierta(pts[0], unitario(pts[1], pts[0]), color, grosor, 20, 10)


def numero(cx, cy, n):
    c.d.ellipse(
        [
            (cx - 17) * ESCALA,
            (cy - 17) * ESCALA,
            (cx + 17) * ESCALA,
            (cy + 17) * ESCALA,
        ],
        fill=AZUL,
        outline=BLANCO,
        width=2 * ESCALA,
    )
    c.texto(cx, cy, str(n), "b", 20, BLANCO, "mm")


# Cliente y coordinador
banda(30, 250, "CLIENTE Y COORDINADOR (un solo programa en el equipo del usuario)")
caja(
    70,
    100,
    420,
    225,
    "Cliente de línea de comandos",
    "el analista pide el archivo y el número de particiones",
)
caja(
    470,
    100,
    830,
    225,
    "Coordinador",
    "cola de particiones, reparto, reintentos y reloj",
)
caja(
    880,
    100,
    1230,
    225,
    "Consolidador",
    "suma los parciales y los compara con la verdad",
    relleno=CLARO2,
)
flecha([(420, 162), (470, 162)])
flecha([(830, 162), (880, 162)])

# Comunicación con los nodos
flecha([(650, 250), (650, 305)], doble=True)
numero(690, 277, 1)
c.texto(
    722,
    277,
    "HTTP y JSON, tiempo máximo de 120 s por solicitud",
    "n",
    19,
    NEGRO,
    "lm",
)

# Nodos
banda(305, 575, "NODOS TRABAJADORES (servicios FastAPI en contenedores Docker)")
nodos_x = [(70, 345), (365, 640), (660, 935), (955, 1230)]
etiquetas = [
    ("Nodo 1", "1 CPU y 512 MB\npuerto 8001"),
    ("Nodo 2", "1 CPU y 512 MB\npuerto 8002"),
    ("Nodos 3 a 5", "1 CPU y 512 MB\npuertos 8003 a 8005"),
    ("Nodo 6", "1 CPU y 512 MB\npuerto 8006"),
]
for (x0, x1), (t, s) in zip(nodos_x, etiquetas):
    caja(x0, 375, x1, 505, t, s)
c.texto(
    70,
    540,
    "Cada nodo atiende una partición a la vez, lee solo su rango y devuelve sumas parciales",
    "i",
    18,
    GRIS_O,
    "lm",
)

# Almacenamiento
flecha([(650, 575), (650, 630)])
numero(690, 602, 2)
c.texto(
    722, 602, "lectura de un rango de bytes, solo lectura", "n", 19, NEGRO, "lm"
)
banda(630, 800, "ALMACENAMIENTO")
caja(
    70,
    695,
    640,
    780,
    "Volumen de Docker procdist_datos",
    "archivos CSV de ventas, montado en modo solo lectura",
)
caja(
    720,
    695,
    1230,
    780,
    "Verdad independiente",
    "totales del generador, solo para comprobar",
    relleno=BLANCO,
    borde=GRIS_O,
    guiones=True,
)

# Red y operación
banda(830, 1010, "RED Y OPERACIÓN")
caja(
    70,
    895,
    440,
    990,
    "Red virtual de Docker",
    "puertos publicados solo en 127.0.0.1",
)
caja(
    470,
    895,
    830,
    990,
    "Comprobación de salud",
    "GET /salud cada 10 s en cada contenedor",
)
caja(
    860,
    895,
    1230,
    990,
    "Límites por contenedor",
    "1 CPU, 512 MB y 100 procesos como máximo",
)
c.texto(
    1260,
    1040,
    "Si un nodo no responde, el coordinador lo retira y reasigna su partición",
    "i",
    17,
    GRIS_O,
    "rm",
)

destino = pathlib.Path(__file__).resolve().parent / "arquitectura_final.png"
c.guardar(str(destino))
print(destino)
