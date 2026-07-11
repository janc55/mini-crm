"""Entry point para Gunicorn.

Gunicorn corre: gunicorn wsgi:app
"""
from app import app

if __name__ == '__main__':
    app.run()
