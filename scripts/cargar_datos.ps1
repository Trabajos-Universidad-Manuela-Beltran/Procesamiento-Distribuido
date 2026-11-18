# Copia los CSV de datos\ al volumen de Docker que leen los nodos (un disco local de Linux dentro de Docker Desktop).
# Montar la carpeta de Windows directamente hacía lenta la lectura: ver evidencias\diagnostico_bind_mount.txt
$raiz = Split-Path -Parent $PSScriptRoot
docker volume create procdist_datos | Out-Null
docker run --rm --user root --entrypoint sh -v procdist_datos:/destino -v "${raiz}\datos:/origen:ro" procdist-nodo:1.0 -c "cp /origen/*.csv /destino/ && ls -la /destino"
