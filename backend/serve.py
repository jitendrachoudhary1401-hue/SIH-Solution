import os
from waitress import serve
from app import create_app

app = create_app()
serve(app, host=os.getenv("API_HOST", "127.0.0.1"), port=int(os.getenv("API_PORT", "5000")))
