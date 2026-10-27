"""Transactional email through Twilio SendGrid; credentials stay server-side."""
import json
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
from urllib.parse import urlsplit
from flask import current_app


def configured():
    settings = current_app.config
    return all(settings.get(key) for key in ("SENDGRID_API_KEY", "SENDGRID_FROM_EMAIL"))


def reset_url(token):
    base = current_app.config["PUBLIC_APP_URL"].rstrip("/")
    url = urlsplit(base)
    local = url.hostname in {"127.0.0.1", "localhost", "::1"}
    if (not url.hostname or url.username or url.password or url.query or url.fragment
            or url.scheme not in {"http", "https"}
            or url.scheme != "https" and (not local or current_app.config["APP_ENV"] == "production")):
        raise ValueError("PUBLIC_APP_URL must be a trusted HTTPS application URL (local HTTP is allowed for development).")
    # URL fragments are not sent to servers or included in access logs.
    return base + "/reset-password#token=" + token


def send_email(recipient, subject, body):
    settings = current_app.config
    if not configured():
        raise RuntimeError("SendGrid delivery is not configured")
    payload = {
        "personalizations": [{"to": [{"email": recipient}]}],
        "from": {"email": settings["SENDGRID_FROM_EMAIL"], "name": settings["SENDGRID_FROM_NAME"]},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
        "tracking_settings": {"click_tracking": {"enable": False, "enable_text": False}, "open_tracking": {"enable": False}},
    }
    request = Request("https://api.sendgrid.com/v3/mail/send", data=json.dumps(payload).encode(), method="POST",
                      headers={"Authorization": "Bearer " + settings["SENDGRID_API_KEY"], "Content-Type": "application/json"})
    with build_opener(NoRedirects()).open(request, timeout=15) as response:
        if response.status != 202:
            raise RuntimeError("SendGrid did not accept the email")


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "Email API redirects are not permitted", headers, fp)
