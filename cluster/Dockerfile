FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# El nodo solo necesita FastAPI y uvicorn; httpx lo usa únicamente el coordinador.
COPY requirements-nodo.txt .
RUN pip install --no-cache-dir -r requirements-nodo.txt

COPY procdist ./procdist
COPY cluster/trabajador.py ./cluster/trabajador.py
RUN touch cluster/__init__.py && useradd --no-create-home --uid 10001 nodo

USER nodo
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/salud', timeout=2)"
CMD ["uvicorn", "cluster.trabajador:app", "--host", "0.0.0.0", "--port", "8000"]
