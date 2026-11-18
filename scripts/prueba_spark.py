"""Comprueba que Spark local calcula lo mismo que la verdad del generador."""

import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.stdout.reconfigure(encoding="utf-8")

from procdist.nucleo import coincide_con_verdad  # noqa: E402
from procdist.spark_ejecutor import con_spark  # noqa: E402

if __name__ == "__main__":
    ruta = RAIZ / "datos" / "ventas_100k.csv"
    verdad = json.loads(
        ruta.with_suffix(".verdad.json").read_text(encoding="utf-8")
    )
    r = con_spark(str(ruta))
    print(
        r.modo,
        f"{r.segundos_total:.2f} s",
        "coincide con la verdad:",
        coincide_con_verdad(r.resultado, verdad),
    )
    print(r.resultado["top5_productos"])
