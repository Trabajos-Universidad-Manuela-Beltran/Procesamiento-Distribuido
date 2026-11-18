"""Diagrama de arquitectura del procesamiento distribuido de ventas (PNG). Usa la biblioteca de dibujo de los documentos UMB.

Uso: .venv\\Scripts\\python.exe diagramas\\arquitectura.py
"""

import pathlib
import sys

sys.path.insert(
    0,
    "C:/Users/cuent/Documents/Universidad/Katherin/2026-02/Sistemas Transaccionales/herramientas_doc/build",
)
from dibujo import (
    AZUL,
    BLANCO,
    CLARO,
    CLARO2,
    ESCALA,
    GRIS_O,
    NEGRO,
    Lienzo,
    unitario,
)  # noqa: E402

W, H = 1300, 1250
c = Lienzo(W, H)


def banda(y0, y1, titulo):
    c.rect(40, y0, 1260, y1, relleno=(250, 251, 253), borde=AZUL, grosor=3)
    c.rect(40, y0, 1260, y0 + 46, relleno=AZUL, borde=AZUL, grosor=3)
    c.texto(650, y0 + 23, titulo, "b", 23, BLANCO, "mm")


def caja(
    x0,
    y0,
    x1,
    y1,
    titulo,
    sub="",
    relleno=CLARO,
    borde=AZUL,
    guiones=False,
    tam_t=21,
    tam_s=18,
):
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
        c.texto(
            (x0 + x1) / 2, y0 + (y1 - y0) * 0.27, titulo, "b", tam_t, NEGRO, "mm"
        )
        c.texto_caja(
            x0,
            y0 + (y1 - y0) * 0.45,
            x1,
            y1,
            sub,
            "n",
            tam_s,
            GRIS_O,
            interlinea=1.2,
            margen=10,
            valign="t",
        )
    else:
        c.texto_caja(x0, y0, x1, y1, titulo, "b", tam_t, NEGRO)


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


# 1 · Origen de datos y partición
banda(30, 235, "ORIGEN DE DATOS Y PARTICIONAMIENTO")
caja(
    70,
    100,
    540,
    215,
    "Archivo CSV de ventas",
    "10.000 · 100.000 · 500.000 · 2.000.000 filas (sintéticas)",
)
caja(
    760,
    100,
    1230,
    215,
    "Particionador",
    "divide el archivo en rangos de bytes [inicio, fin)",
)
flecha([(540, 157), (760, 157)])
numero(650, 128, 1)

# 2 · Coordinador
flecha([(650, 235), (650, 290)])
numero(690, 262, 2)
banda(290, 470, "COORDINADOR")
caja(70, 355, 440, 450, "Cola de particiones", "tareas pendientes y reintentos")
caja(
    520, 355, 890, 450, "Reparto y reasignación", "un nodo toma una tarea a la vez"
)
caja(960, 355, 1230, 450, "Reloj", "tiempo total y por partición", relleno=CLARO2)
flecha([(440, 402), (520, 402)], doble=True)

# 3 · Nodos
flecha([(650, 470), (650, 525)], doble=True)
numero(690, 497, 3)
c.texto(722, 497, "HTTP · JSON", "n", 19, NEGRO, "lm")
banda(525, 790, "NODOS TRABAJADORES (fase map)")
nodos_x = [(70, 345), (365, 640), (660, 935), (955, 1230)]
etiquetas = [
    ("Nodo 1", "contenedor · 1 CPU\nlee y suma su rango"),
    ("Nodo 2", "contenedor · 1 CPU\nlee y suma su rango"),
    ("Nodos 3 a 5", "contenedores · 1 CPU\nlee y suma su rango"),
    ("Nodo 6", "contenedor · 1 CPU\nlee y suma su rango"),
]
for (x0, x1), (t, s) in zip(nodos_x, etiquetas):
    caja(x0, 595, x1, 725, t, s, tam_s=18)
c.texto(
    70,
    757,
    "Cada nodo es un servicio HTTP (FastAPI) que lee solo su rango y devuelve un resultado parcial",
    "i",
    18,
    GRIS_O,
    "lm",
)

# 4 · Consolidación
flecha(
    [
        (
            650,
            790,
        ),
        (650, 845),
    ]
)
numero(690, 817, 4)
banda(845, 1005, "CONSOLIDACIÓN (fase reduce)")
caja(70, 910, 420, 985, "Consolidador", "suma los parciales de los nodos")
caja(
    475,
    910,
    825,
    985,
    "Comprobación",
    "filas y totales iguales a la verdad",
    relleno=CLARO2,
)
caja(
    880,
    910,
    1230,
    985,
    "Verdad independiente",
    "totales del generador",
    relleno=BLANCO,
    borde=GRIS_O,
    guiones=True,
)
flecha([(420, 947), (475, 947)])
flecha([(880, 947), (825, 947)], color=GRIS_O)

# 5 · Salidas
flecha([(650, 1005), (650, 1055)])
numero(690, 1030, 5)
banda(1055, 1215, "SALIDAS")
caja(70, 1120, 440, 1200, "Reportes", "ingresos por ciudad, top 5 y por mes")
caja(520, 1120, 890, 1200, "Visualizaciones", "gráficas de tiempos y aceleración")
caja(960, 1120, 1230, 1200, "Bitácora de tiempos", "JSON con eventos y tiempos")

c.texto(
    1260,
    1237,
    "Si un nodo falla, su partición vuelve a la cola y la toma otro nodo",
    "i",
    17,
    GRIS_O,
    "rm",
)

destino = pathlib.Path(__file__).resolve().parent / "arquitectura.png"
c.guardar(str(destino))
print(destino)
