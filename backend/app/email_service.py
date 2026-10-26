import hmac
import hashlib
import os
import secrets
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional, Tuple, Dict, Any, List


# Test mailbox storage for automated tests and local verification without real network credentials
_test_sent_emails: List[Dict[str, Any]] = []
_mock_smtp_delivery_enabled: bool = False
_mock_smtp_should_fail: bool = False
_mock_smtp_fail_message: str = ""


def set_mock_smtp_delivery(enabled: bool = True, should_fail: bool = False, fail_message: str = "") -> None:
    """Configure mock SMTP delivery for automated test suites."""
    global _mock_smtp_delivery_enabled, _mock_smtp_should_fail, _mock_smtp_fail_message
    _mock_smtp_delivery_enabled = enabled
    _mock_smtp_should_fail = should_fail
    _mock_smtp_fail_message = fail_message


def get_test_sent_emails() -> List[Dict[str, Any]]:
    """Retrieve emails recorded during test runs."""
    return list(_test_sent_emails)


def clear_test_sent_emails() -> None:
    """Clear recorded test emails."""
    _test_sent_emails.clear()


def get_last_sent_otp(email: Optional[str] = None) -> Optional[str]:
    """Retrieve the latest OTP sent to an email address in test mode."""
    for item in reversed(_test_sent_emails):
        if email is None or item.get("to") == email:
            return item.get("otp")
    return None


def get_smtp_config() -> Dict[str, Any]:
    """Load and return current SMTP and OTP configuration from environment."""
    return {
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com").strip(),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "email": os.getenv("SMTP_EMAIL", "").strip(),
        "app_password": os.getenv("SMTP_APP_PASSWORD", "").strip(),
        "expiry_minutes": int(os.getenv("OTP_EXPIRY_MINUTES", "5")),
        "max_attempts": int(os.getenv("OTP_MAX_ATTEMPTS", "3")),
        "resend_cooldown": int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "60")),
    }


def validate_smtp_configuration() -> Tuple[bool, Optional[str]]:
    """
    Validate that required Gmail SMTP configuration is set.
    Never exposes secrets in validation feedback.
    """
    cfg = get_smtp_config()
    if not cfg["email"]:
        return False, "SMTP_EMAIL environment variable is not configured."
    if not cfg["app_password"]:
        return False, "SMTP_APP_PASSWORD environment variable is not configured."
    return True, None


def generate_otp() -> str:
    """
    Generate a cryptographically secure 6-digit numeric OTP.
    Preserves leading zeros (e.g. '004128').
    """
    val = secrets.randbelow(1_000_000)
    return f"{val:06d}"


def compute_otp_verifier(secret_key: Optional[str], salt: str, otp: str) -> str:
    """Compute a keyed HMAC-SHA256 verifier for the OTP. Plaintext is never stored in DB."""
    actual_key = (secret_key or os.getenv("SECRET_KEY") or "onecase-production-secret-key-32-bytes-secure").encode("utf-8")
    message = f"{salt}:{otp}".encode("utf-8")
    return hmac.new(actual_key, message, hashlib.sha256).hexdigest()



def verify_otp_verifier(secret_key: str, salt: str, otp_candidate: str, expected_verifier: str) -> bool:
    """Constant-time comparison of OTP verifier against expected verifier."""
    candidate_verifier = compute_otp_verifier(secret_key, salt, otp_candidate)
    return hmac.compare_digest(candidate_verifier, expected_verifier)


def mask_email(email: str) -> str:
    """
    Safely mask an email address for display without disclosing complete identity.
    e.g., 'officer.rb@onecase.demo' -> 'o*********b@onecase.demo'.
    """
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + ("*" * (len(local) - 2)) + local[-1]
    return f"{masked_local}@{domain}"


def build_otp_email_message(to_email: str, sender_email: str, otp: str, expiry_minutes: int) -> EmailMessage:
    """Construct a clean, professional email message with AICTE OneCase branding."""
    msg = EmailMessage()
    msg["Subject"] = f"OneCase Login Verification Code: {otp}"
    msg["From"] = f"OneCase Security <{sender_email}>"
    msg["To"] = to_email

    # Plain text version
    msg.set_content(
        f"OneCase — AICTE Intelligent Institution Complaint Coordination & Tracking System\n\n"
        f"Your one-time login verification code is: {otp}\n\n"
        f"This code will expire in {expiry_minutes} minutes and can only be used once.\n"
        f"Never share this code with anyone. OneCase administrators will never request this code.\n\n"
        f"If you did not initiate this sign-in attempt, please notify your bureau administrator immediately."
    )

    # HTML version with OneCase branding
    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OneCase Verification Code</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b1526; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f1f5f9;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0b1526; padding: 40px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 520px; background-color: #0f2038; border: 1px solid #1e3a66; border-radius: 12px; padding: 36px 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
          <tr>
            <td>
              <div style="font-size: 11px; font-weight: 700; letter-spacing: 1.2px; color: #38bdf8; text-transform: uppercase; margin-bottom: 8px;">
                AICTE OneCase Portal
              </div>
              <h1 style="margin: 0 0 12px 0; font-size: 24px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">
                Login Verification Code
              </h1>
              <p style="margin: 0 0 24px 0; font-size: 14px; line-height: 1.6; color: #94a3b8;">
                A sign-in attempt was initiated for your authorized OneCase account. Use the six-digit verification code below to complete authentication:
              </p>

              <div style="background-color: #071224; border: 1px solid #1e4578; border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 24px;">
                <div style="font-family: 'Courier New', Courier, monospace; font-size: 34px; font-weight: 700; letter-spacing: 10px; color: #38bdf8;">
                  {otp}
                </div>
                <div style="font-size: 12px; color: #64748b; margin-top: 8px;">
                  Valid for {expiry_minutes} minutes · Single-use only
                </div>
              </div>

              <p style="margin: 0 0 16px 0; font-size: 13px; line-height: 1.6; color: #cbd5e1;">
                <strong>Security Reminder:</strong> Do not share this code with anyone. OneCase officers and support staff will never request your verification code.
              </p>
              <p style="margin: 0; font-size: 12px; line-height: 1.6; color: #64748b;">
                If you did not request this login code, please review your account activity or notify your bureau security administrator immediately.
              </p>

              <hr style="border: none; border-top: 1px solid #1e3a66; margin: 28px 0 20px 0;">

              <div style="font-size: 11px; color: #475569; text-align: center; line-height: 1.5;">
                AICTE Intelligent Institution Complaint Coordination & Tracking System<br>
                Automated security transmission · Do not reply to this email
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
    msg.add_alternative(html_content, subtype="html")
    return msg


def send_otp_email(to_email: str, otp: str, expiry_minutes: int = 5) -> Tuple[bool, Optional[str]]:
    """
    Send a 6-digit OTP email to the registered recipient using Gmail SMTP.
    In automated test environments or when mock is enabled, routes to test mailbox.

    Returns:
        (True, None) on successful delivery.
        (False, error_message) on failure without leaking credentials or secrets.
    """
    # 1. Check if mock delivery is explicitly enabled or if running in test environment
    if _mock_smtp_delivery_enabled or os.getenv("TESTING", "").lower() == "true":
        if _mock_smtp_should_fail:
            return False, _mock_smtp_fail_message or "Simulated email delivery failure."
        _test_sent_emails.append({
            "to": to_email,
            "otp": otp,
            "expiry_minutes": expiry_minutes,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })
        return True, None

    # 2. Validate SMTP configuration
    cfg = get_smtp_config()
    valid, err = validate_smtp_configuration()
    if not valid:
        return False, f"Email delivery service not configured: {err}"

    # 3. Deliver via Gmail SMTP with STARTTLS
    try:
        msg = build_otp_email_message(to_email, cfg["email"], otp, expiry_minutes)
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(cfg["email"], cfg["app_password"])
            server.send_message(msg)
        return True, None
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail SMTP authentication failed. Please verify your Gmail address and 16-character App Password."
    except smtplib.SMTPConnectError:
        return False, "Could not connect to Gmail SMTP server (smtp.gmail.com:587). Please verify network access."
    except TimeoutError:
        return False, "Connection to Gmail SMTP server timed out."
    except smtplib.SMTPException as e:
        # Return generic safe message, do not leak internal trace or secrets
        return False, "Failed to deliver OTP email due to an SMTP transmission error."
    except Exception:
        return False, "Unexpected error occurred during email delivery. Please try again shortly."
