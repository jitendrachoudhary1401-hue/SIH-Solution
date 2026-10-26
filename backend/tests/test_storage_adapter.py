import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest


def test_neon_storage_is_private_and_checks_integrity(app, monkeypatch):
    from app import storage
    remote = MagicMock()
    payload = b"synthetic private evidence"
    remote.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=payload))}
    monkeypatch.setattr(storage, "s3_client", lambda: remote)
    with app.app_context():
        app.config.update(STORAGE_BACKEND="neon", STORAGE_BUCKET="assets")
        backend, bucket = storage.put("random-key", payload, "application/pdf")
        assert (backend, bucket) == ("neon", "assets")
        call = remote.put_object.call_args.kwargs
        assert "ACL" not in call and call["CacheControl"] == "private, no-store"
        item = SimpleNamespace(storage_backend="neon", storage_bucket=bucket, key="random-key", size=len(payload), checksum=hashlib.sha256(payload).hexdigest())
        assert storage.read(item) == payload
        item.checksum = "invalid"
        with pytest.raises(ValueError):
            storage.read(item)
