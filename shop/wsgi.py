"""WSGI entry point for gunicorn: `gunicorn shop.wsgi:app`."""

from .app import create_app

app = create_app()
