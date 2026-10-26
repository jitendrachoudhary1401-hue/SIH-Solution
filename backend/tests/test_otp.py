import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from sqlalchemy import select

from app.models import db, now, User, Session, OTPChallenge, AccountLockout
from app.email_service import (
    set_mock_smtp_delivery,
    clear_test_sent_emails,
    get_last_sent_otp,
    get_test_sent_emails,
    build_otp_email_message,
    validate_smtp_configuration,
    compute_otp_verifier,
    verify_otp_verifier,
    mask_email,
    generate_otp,
)


@pytest.fixture(autouse=True)
def reset_test_emails():
    set_mock_smtp_delivery(True)
    clear_test_sent_emails()
    yield
    set_mock_smtp_delivery(True)
    clear_test_sent_emails()


def test_1_successful_otp_generation_and_verification(client, app):
    """Test 1 & 11: Valid password generates OTP; session is created only after OTP verification."""
    email = "officer.rb@onecase.demo"
    password = "TestPassword!2026"

    # Step 1: Login with credentials
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    data = res.json
    assert data.get("otp_required") is True
    assert "challenge_id" in data
    assert data["email"] == mask_email(email)
    challenge_id = data["challenge_id"]

    # Critical security check: No session cookie established before OTP verification
    set_cookie = res.headers.get("Set-Cookie", "")
    assert "onecase_session=" not in set_cookie
    assert client.get("/api/auth/me").status_code == 401

    # Step 2: Retrieve delivered OTP
    otp = get_last_sent_otp(email)
    assert otp is not None
    assert len(otp) == 6
    assert otp.isdigit()

    # Step 3: Verify OTP
    verify_res = client.post("/api/auth/otp/verify", json={"challenge_id": challenge_id, "otp": otp})
    assert verify_res.status_code == 200
    verify_data = verify_res.json
    assert "csrf" in verify_data
    assert verify_data["user"]["email"] == email
    assert "onecase_session=" in verify_res.headers.get("Set-Cookie", "")

    # Step 4: Verify authenticated session works
    me_res = client.get("/api/auth/me", headers={"X-CSRF-Token": verify_data["csrf"]})
    assert me_res.status_code == 200
    assert me_res.json["user"]["email"] == email


def test_2_correct_email_delivery_message_structure(app):
    """Test 2: Email construction includes AICTE branding, plain text, and HTML with OTP."""
    otp = "048291"
    msg = build_otp_email_message("officer@example.gov.in", "sender@gmail.com", otp, 5)
    assert msg["Subject"] == f"OneCase Login Verification Code: {otp}"
    assert "sender@gmail.com" in msg["From"]
    assert msg["To"] == "officer@example.gov.in"

    plain_content = msg.get_body(preferencelist=('plain',)).get_content()
    assert otp in plain_content
    assert "AICTE" in plain_content
    assert "5 minutes" in plain_content

    # Verify HTML alternative
    html_content = msg.get_body(preferencelist=('html',)).get_content()
    assert otp in html_content
    assert "AICTE OneCase Portal" in html_content



def test_3_incorrect_otp_rejection(client):
    """Test 3: Incorrect OTP rejection with remaining attempts feedback."""
    email = "officer.rb@onecase.demo"
    res = client.post("/api/auth/login", json={"email": email, "password": "TestPassword!2026"})
    challenge_id = res.json["challenge_id"]

    wrong_res = client.post("/api/auth/otp/verify", json={"challenge_id": challenge_id, "otp": "000000"})
    assert wrong_res.status_code == 401
    assert "Invalid verification code" in wrong_res.json["error"]["message"]
    assert "2 attempts remaining" in wrong_res.json["error"]["message"]

    # Verify no session cookie set on failure
    assert "onecase_session=" not in wrong_res.headers.get("Set-Cookie", "")


def test_4_otp_expiration_after_five_minutes(client, app):
    """Test 4: OTP expiration after 5 minutes is strictly rejected."""
    email = "officer.rb@onecase.demo"
    res = client.post("/api/auth/login", json={"email": email, "password": "TestPassword!2026"})
    challenge_id = res.json["challenge_id"]
    otp = get_last_sent_otp(email)

    with app.app_context():
        challenge = db.session.get(OTPChallenge, challenge_id)
        challenge.expires_at = now() - timedelta(seconds=1)
        db.session.commit()

    exp_res = client.post("/api/auth/otp/verify", json={"challenge_id": challenge_id, "otp": otp})
    assert exp_res.status_code == 400
    assert "expired" in exp_res.json["error"]["message"].lower()


def test_5_otp_single_use_enforcement(client):
    """Test 5: An OTP challenge cannot be verified more than once."""
    email = "officer.rb@onecase.demo"
    res = client.post("/api/auth/login", json={"email": email, "password": "TestPassword!2026"})
    challenge_id = res.json["challenge_id"]
    otp = get_last_sent_otp(email)

    # First verification succeeds
    first_res = client.post("/api/auth/otp/verify", json={"challenge_id": challenge_id, "otp": otp})
    assert first_res.status_code == 200

    # Replay of the same challenge must be rejected
    second_res = client.post("/api/auth/otp/verify", json={"challenge_id": challenge_id, "otp": otp})
    assert second_res.status_code == 400
    assert "already been used" in second_res.json["error"]["message"]


def test_6_three_incorrect_otp_attempts_blocks_challenge(client, app):
    """Test 6: 3 consecutive incorrect OTP attempts invalidates the challenge."""
    email = "officer.rb@onecase.demo"
    res = client.post("/api/auth/login", json={"email": email, "password": "TestPassword!2026"})
    challenge_id = res.json["challenge_id"]
    real_otp = get_last_sent_otp(email)

    # Attempt 1
    r1 = client.post("/api/auth/otp/verify", json={"challenge_id": challenge_id, "otp": "111111"})
    assert r1.status_code == 401
    assert "2 attempts remaining" in r1.json["error"]["message"]

    # Attempt 2
    r2 = client.post("/api/auth/otp/verify", json={"challenge_id": challenge_id, "otp": "222222"})
    assert r2.status_code == 401
    assert "1 attempt remaining" in r2.json["error"]["message"]

    # Attempt 3 -> invalidates challenge and returns 429
    r3 = client.post("/api/auth/otp/verify", json={"challenge_id": challenge_id, "otp": "333333"})
    assert r3.status_code == 429
    assert "invalidated" in r3.json["error"]["message"].lower()

    # Even with the real OTP, subsequent verification fails
    r4 = client.post("/api/auth/otp/verify", json={"challenge_id": challenge_id, "otp": real_otp})
    assert r4.status_code in (400, 429)


def test_7_resend_invalidates_previous_otp(client, app):
    """Test 7: Resending an OTP invalidates the previous challenge."""
    email = "officer.rb@onecase.demo"
    res1 = client.post("/api/auth/login", json={"email": email, "password": "TestPassword!2026"})
    ch1_id = res1.json["challenge_id"]
    otp1 = get_last_sent_otp(email)

    # Fast forward past cooldown (60 seconds)
    with app.app_context():
        ch1 = db.session.get(OTPChallenge, ch1_id)
        ch1.created_at = now() - timedelta(seconds=65)
        db.session.commit()

    # Request resend
    res2 = client.post("/api/auth/otp/resend", json={"challenge_id": ch1_id})
    assert res2.status_code == 200
    ch2_id = res2.json["challenge_id"]
    assert ch2_id != ch1_id
    otp2 = get_last_sent_otp(email)
    assert otp2 is not None

    # Verifying old challenge with old OTP must fail
    old_verify = client.post("/api/auth/otp/verify", json={"challenge_id": ch1_id, "otp": otp1})
    assert old_verify.status_code in (400, 429)

    # Verifying new challenge with new OTP must succeed
    new_verify = client.post("/api/auth/otp/verify", json={"challenge_id": ch2_id, "otp": otp2})
    assert new_verify.status_code == 200


def test_8_resend_cooldown_and_rate_limits(client, app):
    """Test 8: Cooldown enforced on immediate resend, and 15-minute rate limit."""
    email = "officer.rb@onecase.demo"
    res = client.post("/api/auth/login", json={"email": email, "password": "TestPassword!2026"})
    ch_id = res.json["challenge_id"]

    # Immediate resend within 60s cooldown -> 429
    cool_res = client.post("/api/auth/otp/resend", json={"challenge_id": ch_id})
    assert cool_res.status_code == 429
    assert "wait" in cool_res.json["error"]["message"].lower()

    # Simulate 5 OTP requests within 15 minutes to test account rate limit
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == email))
        for _ in range(5):
            db.session.add(OTPChallenge(
                id=secrets.token_urlsafe(32),
                user_id=user.id,
                email=email,
                otp_verifier="fake-verifier",
                salt="fake-salt",
                expires_at=now() + timedelta(minutes=5),
                created_at=now() - timedelta(minutes=2),
                status="invalidated"
            ))
        db.session.commit()

    # Now login or resend must hit the 15-minute rate limit
    limit_res = client.post("/api/auth/login", json={"email": email, "password": "TestPassword!2026"})
    assert limit_res.status_code == 429
    assert "Too many verification requests" in limit_res.json["error"]["message"]


def test_9_smtp_delivery_failure_handling(client):
    """Test 9: Simulated SMTP failure safely reports error without creating challenge or session."""
    email = "officer.rb@onecase.demo"
    set_mock_smtp_delivery(True, should_fail=True, fail_message="Gmail SMTP connection timed out")

    res = client.post("/api/auth/login", json={"email": email, "password": "TestPassword!2026"})
    assert res.status_code == 503
    assert "Gmail SMTP connection timed out" in res.json["error"]["message"]

    # Verify no session created
    assert "onecase_session=" not in res.headers.get("Set-Cookie", "")


def test_10_missing_smtp_configuration():
    """Test 10: Clear validation errors when SMTP variables are not set."""
    orig_email = os.environ.get("SMTP_EMAIL")
    orig_pass = os.environ.get("SMTP_APP_PASSWORD")

    try:
        os.environ["SMTP_EMAIL"] = ""
        os.environ["SMTP_APP_PASSWORD"] = "test-pass"
        valid, err = validate_smtp_configuration()
        assert valid is False
        assert "SMTP_EMAIL" in err

        os.environ["SMTP_EMAIL"] = "test@example.com"
        os.environ["SMTP_APP_PASSWORD"] = ""
        valid, err = validate_smtp_configuration()
        assert valid is False
        assert "SMTP_APP_PASSWORD" in err
    finally:
        if orig_email is not None:
            os.environ["SMTP_EMAIL"] = orig_email
        else:
            os.environ.pop("SMTP_EMAIL", None)
        if orig_pass is not None:
            os.environ["SMTP_APP_PASSWORD"] = orig_pass
        else:
            os.environ.pop("SMTP_APP_PASSWORD", None)


def test_12_concurrent_verification_requests(app):
    """Test 12: Concurrent verification requests cannot consume the same OTP twice."""
    email = "officer.rb@onecase.demo"
    client = app.test_client()

    res = client.post("/api/auth/login", json={"email": email, "password": "TestPassword!2026"})
    assert res.status_code == 200
    ch_id = res.json["challenge_id"]
    otp = get_last_sent_otp(email)

    def attempt_verify():
        c = app.test_client()
        return c.post("/api/auth/otp/verify", json={"challenge_id": ch_id, "otp": otp})

    # Run 4 simultaneous verification requests
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(attempt_verify) for _ in range(4)]
        results = [f.result() for f in futures]

    statuses = [r.status_code for r in results]
    # Exactly one request must succeed with 200
    assert statuses.count(200) == 1
    # All other concurrent attempts must be rejected with 400 (already consumed)
    assert statuses.count(400) == 3


def test_13_three_failed_passwords_lockout(client, app):
    """Test 13: 3 consecutive failed password attempts trigger 60-second lockout."""
    email = "lead.rb@onecase.demo"

    # Attempt 1 -> 401
    r1 = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword!1"})
    assert r1.status_code == 401

    # Attempt 2 -> 401
    r2 = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword!2"})
    assert r2.status_code == 401

    # Attempt 3 -> 429 lockout triggered
    r3 = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword!3"})
    assert r3.status_code == 429
    assert "locked for 60 seconds" in r3.json["error"]["message"].lower()

    # Attempt 4 with CORRECT password within 60s -> still locked (429)
    r4 = client.post("/api/auth/login", json={"email": email, "password": "TestPassword!2026"})
    assert r4.status_code == 429
    assert "temporarily locked" in r4.json["error"]["message"].lower()

    # Simulate 60 seconds expiration
    with app.app_context():
        lockout = db.session.scalar(select(AccountLockout).where(AccountLockout.email == email))
        lockout.locked_until = now() - timedelta(seconds=1)
        db.session.commit()

    # Now login with correct password works
    r5 = client.post("/api/auth/login", json={"email": email, "password": "TestPassword!2026"})
    assert r5.status_code == 200
    assert r5.json.get("otp_required") is True
