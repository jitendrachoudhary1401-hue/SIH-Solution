"""Apply committed migrations over Neon's direct connection; never print its URL."""
from app import create_app
from flask_migrate import upgrade
from pathlib import Path

app = create_app({"RATELIMIT_ENABLED": False})
with app.app_context():
    upgrade(directory=str(Path(__file__).resolve().parent / "migrations"))
    print("Database migration completed.")
