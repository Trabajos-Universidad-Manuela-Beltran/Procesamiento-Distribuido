"""Imprime un resumen legible de las mediciones guardadas (para revisar cifras antes de redactar)."""

import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
local = json.loads(
    (RAIZ / "evidencias" / "medicion_local.json").read_text(encoding="utf-8")
)
cluster = json.loads(
    (RAIZ / "evidencias" / "medicion_cluster.json").read_text(encoding="utf-8")
)
print(local["hardware"])
for t in local["tamanos"]:
    s = t["secuencial"]
    print(
        f"\n{t['archivo']} ({t['filas']} filas, {t['mb']} MB): secuencial mediana {s['mediana']:.3f} (min {min(s['segundos']):.3f}, max {max(s['segundos']):.3f})"
    )
    for p in ("2", "4", "6", "12"):
        a, h = t["paralelo_con_arranque"][p], t["paralelo_pool_caliente"][p]
        print(
            f"  p={p}: arranque {a['mediana']:.3f} (Ts/Tp {s['mediana']/a['mediana']:.2f}) | caliente {h['mediana']:.3f} "
            f"(min {min(h['segundos']):.3f}, max {max(h['segundos']):.3f}; Ts/Tp {s['mediana']/h['mediana']:.2f})"
        )
    sp = t["spark_local"]
    print(f"  spark: {sp['mediana']:.3f} {[round(x, 2) for x in sp['segundos']]}")
for e in cluster["escalado"]:
    print(
        e["archivo"],
        e["nodos"],
        "nodos",
        f"{e['mediana']:.3f}",
        [round(x, 2) for x in e["segundos"]],
    )
for f in cluster["fallas"]:
    print(
        f["escenario"],
        f["correcto"],
        f["resultado"]["filas"],
        f["particiones_perdidas"],
        f["nodos_caidos"],
        round(f["segundos_total"], 2),
    )
