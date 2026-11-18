$env:PATH = "G:\.venv\Scripts;$env:PATH"
Set-Location G:\
Comentario 'Procesamiento de 100.000 registros: secuencial y paralelo con 4 procesos (primeras líneas)'
Ejecutar 'python scripts\ejecutar.py --archivo datos\ventas_100k.csv --procesos 4 | Select-Object -First 21'
