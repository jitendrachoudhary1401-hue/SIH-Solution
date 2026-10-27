"""Apply committed migrations over Neon's direct connection; never print its URL."""
from app import create_app
from flask_migrate import upgrade
from pathlib import Path

app = create_app({"RATELIMIT_ENABLED": False})
with app.app_context():
    upgrade(directory=str(Path(__file__).resolve().parent / "migrations"))
    print("Database migration completed.")
    if app.config["DEMO_ACCOUNTS_ENABLED"]:
        from app.demo import seed_public_demo_accounts
        created = seed_public_demo_accounts()
        print(f"Public demo accounts ready ({created} created).")
