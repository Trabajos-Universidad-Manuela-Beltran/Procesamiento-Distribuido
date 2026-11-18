$env:PATH = "G:\.venv\Scripts;$env:PATH"
Set-Location G:\
Comentario 'Clúster de 4 nodos con 500.000 registros y 8 particiones'
Write-Host -NoNewline 'PS> ' -ForegroundColor Green; Write-Host '$n = "http://127.0.0.1:8001","http://127.0.0.1:8002","http://127.0.0.1:8003","http://127.0.0.1:8004"'
$n = "http://127.0.0.1:8001","http://127.0.0.1:8002","http://127.0.0.1:8003","http://127.0.0.1:8004"
Ejecutar 'python cluster\coordinador.py --archivo ventas_500k.csv --nodos $n --particiones 8'
