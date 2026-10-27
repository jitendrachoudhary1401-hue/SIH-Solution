"""Reject excess traffic before route authentication or database work.

Memory storage is only for this single-process local demo. A production replica
set must use one Redis backend; storage errors fail closed without DB fallback.
"""
import hashlib
import os
from flask import request
from flask_limiter import Limiter
from .network import client_address


def configure(app):
    storage = os.getenv("RATE_LIMIT_STORAGE_URI", "memory://")
    app.config.setdefault("RATELIMIT_STORAGE_URI", storage)
    app.config.setdefault("RATELIMIT_ENABLED", True)
    if app.config["APP_ENV"] == "production" and not str(app.config["RATELIMIT_STORAGE_URI"]).startswith(("redis://", "rediss://")):
        raise RuntimeError("Production rate limiting requires a shared Redis storage URI")
    identity = lambda: hashlib.sha256(client_address().encode()).hexdigest()
    limiter = Limiter(key_func=identity, default_limits=[os.getenv("RATE_LIMIT_DEFAULT", "120 per minute"), "2000 per hour"],
                      headers_enabled=True, storage_uri=app.config["RATELIMIT_STORAGE_URI"],
                      swallow_errors=False, in_memory_fallback_enabled=False)
    limiter.init_app(app)
    limiter.request_filter(lambda: not request.path.startswith("/api/") or request.path == "/api/health")
    writes = limiter.shared_limit(os.getenv("RATE_LIMIT_WRITES", "30 per minute"), scope="all-database-writes", methods=["POST", "PATCH", "PUT", "DELETE"])
    for endpoint, view in list(app.view_functions.items()):
        if endpoint in {"frontend", "health"}:
            continue
        wrapped = writes(view)
        if endpoint in {"api.login", "api.signup", "demo.demo_login"}:
            wrapped = limiter.limit(os.getenv("RATE_LIMIT_LOGIN", "5 per minute"), override_defaults=False)(wrapped)
        elif endpoint == "password_reset.forgot_password":
            def reset_account_key():
                data = request.get_json(silent=True)
                email = str(data.get("email", ""))[:180].strip().lower() if isinstance(data, dict) else ""
                return hashlib.sha256(email.encode()).hexdigest()
            wrapped = limiter.limit("3 per hour", key_func=reset_account_key, override_defaults=False)(wrapped)
            wrapped = limiter.limit("5 per minute", override_defaults=False)(wrapped)
        elif endpoint == "password_reset.reset_password":
            wrapped = limiter.limit("10 per minute", override_defaults=False)(wrapped)
        elif endpoint == "api.upload":
            wrapped = limiter.limit("10 per hour", override_defaults=False)(wrapped)
        elif endpoint == "api.retry_matching":
            wrapped = limiter.limit("5 per hour", override_defaults=False)(wrapped)
        elif endpoint.startswith("administration."):
            wrapped = limiter.limit("30 per minute", methods=["POST", "PATCH", "DELETE"], override_defaults=False)(wrapped)
        app.view_functions[endpoint] = wrapped
    app.extensions["onecase_limiter"] = limiter
