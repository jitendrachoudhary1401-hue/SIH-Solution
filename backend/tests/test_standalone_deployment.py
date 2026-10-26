"""A Render folder deployment must not depend on workspace files or envs."""
import os
from pathlib import Path
import shutil
import subprocess
import sys


def test_backend_folder_alone_can_migrate_and_serve(tmp_path):
    source = Path(__file__).resolve().parents[1]
    service = tmp_path / "service"
    shutil.copytree(source, service, ignore=shutil.ignore_patterns(
        ".env", ".env.*", ".runtime", ".venv", "__pycache__", ".pytest_cache", "tests"))
    environment = {key: value for key, value in os.environ.items()
                   if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE"}}
    environment.update(APP_ENV="development", STORAGE_BACKEND="local", RATE_LIMIT_STORAGE_URI="memory://")
    environment.update(NEON_STORAGE_ENDPOINT="https://neon-storage.example.test",
                       NEON_STORAGE_REGION="synthetic-region", NEON_STORAGE_ACCESS_KEY_ID="synthetic-key",
                       NEON_STORAGE_SECRET_ACCESS_KEY="synthetic-secret")
    check = """
from pathlib import Path
from app import create_app
from flask_migrate import upgrade
app = create_app({'TESTING': True, 'RATELIMIT_ENABLED': False})
assert Path(app.config['STORAGE_PATH']).is_relative_to(Path.cwd())
assert Path(app.config['MODEL_PATH']).is_relative_to(Path.cwd())
assert app.config['AWS_ENDPOINT_URL_S3'] == 'https://neon-storage.example.test'
assert app.config['AWS_REGION'] == 'synthetic-region'
assert app.config['AWS_ACCESS_KEY_ID'] == 'synthetic-key'
assert app.config['AWS_SECRET_ACCESS_KEY'] == 'synthetic-secret'
with app.app_context():
    upgrade(directory='migrations')
assert app.test_client().get('/api/health').status_code == 200
assert app.test_client().get('/officer/login').status_code == 404
print('PASS backend-only migration and health; no workspace/frontend/env files')
"""
    result = subprocess.run([sys.executable, "-c", check], cwd=service, env=environment,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
