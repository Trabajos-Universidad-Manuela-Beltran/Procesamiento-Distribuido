$env:PATH = "G:\.venv\Scripts;$env:PATH"
Set-Location G:\
Comentario 'Análisis estático del código con bandit'
Ejecutar 'python -m bandit -q -r procdist cluster scripts datos -x tests | Select-Object -Last 17'
Comentario 'Vulnerabilidades conocidas en las dependencias'
Ejecutar 'python -m pip_audit -r requirements.txt'
