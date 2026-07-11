FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencias del sistema para compilar extensiones (oauth2client, gspread)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python primero (mejor cache de capas Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el codigo
COPY . .

# Crear usuario no-root por seguridad
# Tambien crea /app/data donde se montara el volumen persistente (crm.db + credentials.json)
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

# Exponer puerto
EXPOSE 5000

# Gunicorn con 1 worker (necesario para APScheduler, sino corre N veces)
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
