$env:PATH = "G:\.venv\Scripts;$env:PATH"
Set-Location G:\
Comentario 'Pruebas automáticas con cobertura (incluye nodos reales y Spark local)'
Ejecutar 'python -m pytest -q --cov=procdist --cov=cluster'
