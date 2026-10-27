"""ASGI entry point: uvicorn main:app --reload --port 5000 (from backend)."""
from asgiref.wsgi import WsgiToAsgi
from app import create_app

flask_app = create_app()
app = WsgiToAsgi(flask_app)
