"""Exercise the Uvicorn entry point against the isolated test database."""
import asyncio
import json
from pathlib import Path
import runpy
from asgiref.testing import ApplicationCommunicator


def test_backend_serves_only_api_even_when_frontend_build_exists(app, client, tmp_path):
    build = tmp_path / "frontend-dist"
    build.mkdir()
    (build / "index.html").write_text("<html>Frontend build</html>", encoding="utf-8")
    (build / "logo.png").write_bytes(b"frontend asset")
    app.config["FRONTEND_PATH"] = str(build)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json == {"service": "onecase", "message": "Backend API", "health": "/api/health"}
    for path in ("/officer/login", "/register/student-parent", "/logo.png", "/api/unknown"):
        response = client.get(path)
        assert response.status_code == 404 and response.is_json


def test_main_asgi_adapter_serves_health_and_persists_registration(app, monkeypatch):
    monkeypatch.setattr("app.create_app", lambda: app)
    application = runpy.run_path(str(Path(__file__).resolve().parents[1] / "main.py"))["app"]

    async def request(path, method="GET", data=None):
        body = json.dumps(data).encode() if data else b""
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
                 "scheme": "http", "path": path, "root_path": "", "query_string": b"",
                 "headers": [(b"host", b"localhost"), (b"content-type", b"application/json"),
                             (b"content-length", str(len(body)).encode())],
                 "server": ("localhost", 5000), "client": ("127.0.0.1", 12345)}
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request", "body": body})
        response = await communicator.receive_output(timeout=10)
        content = b""
        while True:
            part = await communicator.receive_output(timeout=10)
            content += part.get("body", b"")
            if not part.get("more_body", False):
                break
        await communicator.wait(timeout=10)
        return response["status"], json.loads(content)

    async def check():
        status, health = await request("/api/health")
        assert status == 200 and health["status"] == "ok"
        status, result = await request("/api/auth/register", "POST", {
            "name": "ASGI Account", "email": "asgi-student@example.com", "account_type": "student",
            "password": "ASGIPassphrase!2026", "confirm_password": "ASGIPassphrase!2026"})
        assert status == 201 and result["approval_pending"] is False
        status, identity = await request("/api/auth/login", "POST", {
            "email": "asgi-student@example.com", "password": "ASGIPassphrase!2026"})
        assert status == 200 and identity["user"]["role"] == "student"

    asyncio.run(check())
