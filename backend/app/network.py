"""Only the authenticated application proxy may supply a client address."""
import hmac
from ipaddress import ip_address
from flask import current_app, request


def client_address():
    secret = current_app.config.get("FRONTEND_PROXY_SECRET", "")
    if secret and hmac.compare_digest(secret, request.headers.get("X-OneCase-Proxy-Key", "")):
        try:
            return str(ip_address(request.headers.get("X-OneCase-Client-IP", "")))
        except ValueError:
            pass
    return request.remote_addr or "unknown"
