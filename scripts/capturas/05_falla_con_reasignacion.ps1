$env:PATH = "G:\.venv\Scripts;$env:PATH"
Set-Location G:\
Comentario 'Se apaga a propósito el nodo que recibe la partición 3; el coordinador reasigna'
Write-Host -NoNewline 'PS> ' -ForegroundColor Green; Write-Host '$n = "http://127.0.0.1:8001","http://127.0.0.1:8002","http://127.0.0.1:8003","http://127.0.0.1:8004"'
$n = "http://127.0.0.1:8001","http://127.0.0.1:8002","http://127.0.0.1:8003","http://127.0.0.1:8004"
Ejecutar 'python cluster\coordinador.py --archivo ventas_500k.csv --nodos $n --particiones 8 --falla-en 3'
Comentario 'Estado de los contenedores después de la falla'
Ejecutar 'docker compose ps -a --format "table {{.Name}}\t{{.Status}}"'
