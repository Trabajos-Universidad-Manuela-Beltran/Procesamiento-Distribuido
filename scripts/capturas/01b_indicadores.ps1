$env:PATH = "G:\.venv\Scripts;$env:PATH"
Set-Location G:\
Comentario 'Indicadores calculados (mismo comando, líneas restantes)'
Ejecutar 'python scripts\ejecutar.py --archivo datos\ventas_100k.csv --procesos 4 | Select-Object -Skip 21'
