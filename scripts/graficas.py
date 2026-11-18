"""Genera las gráficas del informe a partir de evidencias/medicion_local.json y evidencias/medicion_cluster.json."""

import json
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "evidencias" / "graficas"
sys.stdout.reconfigure(encoding="utf-8")

AZUL, AZUL2, GRIS, GRIS_C, NEGRO = (
    "#1F497D",
    "#4F81BD",
    "#595959",
    "#A6A6A6",
    "#1E1E1E",
)
plt.rcParams.update(
    {
        "font.family": "Times New Roman",
        "font.size": 11,
        "axes.edgecolor": GRIS,
        "axes.labelcolor": NEGRO,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#E3E3E3",
        "grid.linewidth": 0.8,
        "legend.frameon": False,
        "savefig.dpi": 200,
    }
)


def coma(valor, _pos=None) -> str:
    """Formato español: coma decimal y punto de miles."""
    texto = (
        f"{valor:,.2f}".rstrip("0").rstrip(".")
        if abs(valor) < 1000
        else f"{valor:,.0f}"
    )
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def guardar(fig, nombre: str) -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(SALIDA / nombre, facecolor="white")
    plt.close(fig)
    print("guardada", SALIDA / nombre)


def grafica_tiempos(local: dict) -> None:
    filas = [t["filas"] for t in local["tamanos"]]
    fig, ax = plt.subplots(figsize=(6.5, 3.9))
    series = [
        (
            "Secuencial",
            [t["secuencial"]["mediana"] for t in local["tamanos"]],
            GRIS,
            "o",
            "-",
        ),
        (
            "Paralelo, 12 procesos (con arranque)",
            [t["paralelo_con_arranque"]["12"]["mediana"] for t in local["tamanos"]],
            AZUL2,
            "s",
            "--",
        ),
        (
            "Paralelo, 12 procesos (procesos ya creados)",
            [
                t["paralelo_pool_caliente"]["12"]["mediana"]
                for t in local["tamanos"]
            ],
            AZUL,
            "s",
            "-",
        ),
        (
            "Spark local",
            [t["spark_local"]["mediana"] for t in local["tamanos"]],
            GRIS_C,
            "^",
            "-.",
        ),
    ]
    for nombre, ys, color, marca, estilo in series:
        ax.plot(
            filas,
            ys,
            color=color,
            marker=marca,
            linestyle=estilo,
            linewidth=2,
            markersize=6,
            label=nombre,
        )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks(filas)
    ax.xaxis.set_major_formatter(FuncFormatter(coma))
    ax.yaxis.set_major_formatter(FuncFormatter(coma))
    ax.set_xlabel("Número de registros")
    ax.set_ylabel("Tiempo (s), mediana de 5 corridas")
    ax.legend(loc="upper left", fontsize=9)
    guardar(fig, "tiempos_por_tamano.png")


def grafica_aceleracion(local: dict) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 3.9))
    procesos = [2, 4, 6, 12]
    estilos = {"ventas_500k.csv": (AZUL2, "o"), "ventas_2m.csv": (AZUL, "s")}
    desplazamiento = {
        "ventas_500k.csv": (0, -15),
        "ventas_2m.csv": (0, 8),
    }  # evita que las etiquetas se pisen
    for t in local["tamanos"]:
        if t["archivo"] not in estilos:
            continue
        color, marca = estilos[t["archivo"]]
        base = t["secuencial"]["mediana"]
        ys = [
            base / t["paralelo_pool_caliente"][str(p)]["mediana"] for p in procesos
        ]
        ax.plot(
            procesos,
            ys,
            color=color,
            marker=marca,
            linewidth=2,
            label=f"{coma(t['filas'])} registros",
        )
        for x, y in zip(procesos, ys):
            ax.annotate(
                coma(y),
                (x, y),
                textcoords="offset points",
                xytext=desplazamiento[t["archivo"]],
                ha="center",
                fontsize=9,
                color=color,
            )
    ax.plot(
        [1, 6, 12],
        [1, 6, 6],
        color=GRIS_C,
        linestyle=":",
        linewidth=1.8,
        label="Ideal (6 núcleos físicos)",
    )
    ax.set_xticks([1] + procesos)
    ax.set_xlabel("Procesos")
    ax.set_ylabel("Aceleración Ts / Tp")
    ax.yaxis.set_major_formatter(FuncFormatter(coma))
    ax.legend(loc="upper left", fontsize=9)
    guardar(fig, "aceleracion_local.png")


def grafica_cluster(cluster: dict) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 3.9))
    estilos = {"ventas_500k.csv": (AZUL2, "o"), "ventas_2m.csv": (AZUL, "s")}
    nombres = {
        "ventas_500k.csv": "500.000 registros",
        "ventas_2m.csv": "2.000.000 registros",
    }
    for archivo, (color, marca) in estilos.items():
        filas = [e for e in cluster["escalado"] if e["archivo"] == archivo]
        if not filas:
            continue
        base = filas[0]["mediana"]
        xs = [e["nodos"] for e in filas]
        ys = [base / e["mediana"] for e in filas]
        ax.plot(
            xs, ys, color=color, marker=marca, linewidth=2, label=nombres[archivo]
        )
        for x, y in zip(xs, ys):
            ax.annotate(
                coma(y),
                (x, y),
                textcoords="offset points",
                xytext=(0, 7),
                ha="center",
                fontsize=9,
                color=color,
            )
    ax.plot(
        [1, 6], [1, 6], color=GRIS_C, linestyle=":", linewidth=1.8, label="Ideal"
    )
    ax.set_xticks([1, 2, 4, 6])
    ax.set_xlabel("Nodos (contenedores de 1 CPU)")
    ax.set_ylabel("Aceleración respecto a 1 nodo")
    ax.yaxis.set_major_formatter(FuncFormatter(coma))
    ax.legend(loc="upper left", fontsize=9)
    guardar(fig, "aceleracion_cluster.png")


if __name__ == "__main__":
    local = json.loads(
        (RAIZ / "evidencias" / "medicion_local.json").read_text(encoding="utf-8")
    )
    grafica_tiempos(local)
    grafica_aceleracion(local)
    cluster_json = RAIZ / "evidencias" / "medicion_cluster.json"
    if cluster_json.exists():
        grafica_cluster(json.loads(cluster_json.read_text(encoding="utf-8")))
