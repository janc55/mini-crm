"""Configuracion de Gunicorn para produccion.

Notas importantes:
- 1 worker es CRITICO porque APScheduler corre en proceso.
  Con multiples workers, el backup automatico correria N veces.
- 2 threads por worker es suficiente para este trafico.
- Timeout amplio porque la primera request puede tardar (conexion a Google Sheets).
"""
import multiprocessing

bind = "0.0.0.0:5000"
workers = 1
threads = 2
timeout = 120
graceful_timeout = 30
keepalive = 5

# Logs a stdout/stderr (los captura Dokploy)
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Limites
max_requests = 1000
max_requests_jitter = 50
