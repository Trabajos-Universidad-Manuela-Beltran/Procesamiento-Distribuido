# Procesamiento distribuido de datos de ventas

Práctica de la guía S14 a S16 de Sistemas Distribuidos (UMB). Calcula tres indicadores sobre un archivo CSV de ventas sintéticas
(ingreso por ciudad, top 5 de productos por cantidad e ingreso por mes) de cuatro formas y compara tiempos y resultados:

| Modo | Dónde corre |
|---|---|
| Secuencial | Un proceso (línea base) |
| Paralelo | Varios procesos de Python en el mismo equipo |
| Apache Spark | `local[*]`: hilos de una sola máquina |
| Clúster | Seis contenedores Docker (1 CPU y 512 MB cada uno) coordinados por HTTP |

El clúster es de contenedores en **una sola máquina**: comparte procesador, memoria y disco. Sirve para estudiar el reparto,
la coordinación y las fallas, no para predecir el rendimiento de una red física.

## Cómo funciona

El archivo se divide en rangos de bytes. Cada partición procesa las líneas que empiezan dentro de su rango y devuelve sumas
parciales (fase *map*); el consolidador las suma (fase *reduce*). Al generar los datos se guarda un `.verdad.json` calculado
con código independiente, y cada modo compara su resultado con él.

## Estructura

```
datos/generar_ventas.py     generador de ventas sintéticas + verdad independiente
procdist/                   núcleo (partición, map, reduce), modos secuencial/paralelo y Spark
cluster/                    nodo (FastAPI), coordinador y Dockerfile
docker-compose.yml          clúster de seis nodos
scripts/                    ejecución, mediciones, gráficas y carga de datos
tests/                      32 pruebas (pytest), cobertura 91 %
evidencias/                 mediciones en JSON, salidas de consola y gráficas
diagramas/                  diagrama de arquitectura
```

## Uso (Windows, desde esta carpeta)

```
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# Datos (semilla fija). ventas_2m.csv no se guarda por su tamaño: se regenera con este mismo comando.
.venv\Scripts\python.exe datos\generar_ventas.py --n 100000 --salida datos\ventas_100k.csv
.venv\Scripts\python.exe datos\generar_ventas.py --n 2000000 --salida datos\ventas_2m.csv

# Procesar y comparar con la verdad
.venv\Scripts\python.exe scripts\ejecutar.py --archivo datos\ventas_100k.csv --procesos 4
.venv\Scripts\python.exe scripts\ejecutar.py --archivo datos\ventas_100k.csv --procesos 4 --falla-en 2 --sin-reintento

# Pruebas
.venv\Scripts\python.exe -m pytest --cov=procdist --cov=cluster

# Clúster de contenedores (Docker Desktop encendido)
docker compose build
powershell -File scripts\cargar_datos.ps1            # copia los CSV a un volumen de Docker
docker compose up -d
.venv\Scripts\python.exe cluster\coordinador.py --archivo ventas_500k.csv --nodos http://127.0.0.1:8001 http://127.0.0.1:8002
docker compose down; docker volume rm procdist_datos

# Mediciones y gráficas
.venv\Scripts\python.exe scripts\medir_local.py --repeticiones 5 --tamanos 10k 100k 500k 2m --spark
.venv\Scripts\python.exe scripts\medir_cluster.py --repeticiones 5
.venv\Scripts\python.exe scripts\graficas.py

# Concurrencia: lanza todas las particiones a la vez contra nodos locales (sin Docker)
.venv\Scripts\python.exe scripts\prueba_concurrencia.py
```

Leer los CSV desde la carpeta de Windows montada en los contenedores fue unas cinco veces más lento que desde un volumen de
Docker (`evidencias/diagnostico_bind_mount.txt`); por eso el compose usa un volumen.

## Resultados principales (portátil i7-9750H, 6 núcleos físicos; mediana de 5 corridas)

Con 2.000.000 de registros: secuencial 18,86 s; 12 procesos con el grupo ya creado 2,88 s (aceleración 6,56); clúster de 1 nodo
24,19 s y de 6 nodos 7,53 s (aceleración 3,21). Con 10.000 registros distribuir es más lento que el secuencial. Detalle,
análisis y limitaciones en el informe Word/PDF de la carpeta `documentos`.

## Seguridad

El nodo valida el nombre de archivo y los rangos, y solo lee su directorio de datos. Los contenedores corren sin privilegios,
con sistema de archivos de solo lectura, sin capacidades extra, con límites de CPU, memoria y procesos y puertos solo en
`127.0.0.1`. La caída simulada (`simular_caida`) solo se acepta si el nodo tiene `PERMITIR_CAIDA_SIMULADA=1`.
`bandit` no reporta hallazgos medios ni altos y `pip-audit` no reporta vulnerabilidades conocidas (`evidencias/seguridad.txt`).
