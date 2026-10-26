"""Private evidence storage. All credentials are server-only environment settings.

Existing local evidence keeps its original backend; new Neon evidence uses a
private branch-scoped bucket. No public or presigned URLs are exposed to clients.
"""
import hashlib
from pathlib import Path
from flask import current_app


def s3_client():
    import boto3
    from botocore.config import Config
    settings = current_app.config
    if not all(settings.get(k) for k in ("AWS_ENDPOINT_URL_S3", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION")):
        raise RuntimeError("Neon object-storage environment configuration is incomplete")
    return boto3.client("s3", endpoint_url=settings["AWS_ENDPOINT_URL_S3"], region_name=settings["AWS_REGION"],
                        aws_access_key_id=settings["AWS_ACCESS_KEY_ID"], aws_secret_access_key=settings["AWS_SECRET_ACCESS_KEY"],
                        config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                                      connect_timeout=5, read_timeout=15, retries={"max_attempts": 2, "mode": "standard"}))


def put(key, content, media_type):
    backend = current_app.config["STORAGE_BACKEND"]
    if backend == "neon":
        bucket = current_app.config["STORAGE_BUCKET"]
        s3_client().put_object(Bucket=bucket, Key=key, Body=content, ContentType=media_type,
                              Metadata={"sha256": hashlib.sha256(content).hexdigest()}, CacheControl="private, no-store")
        return backend, bucket
    if backend != "local":
        raise RuntimeError("Unknown private evidence storage backend")
    (Path(current_app.config["STORAGE_PATH"]) / key).write_bytes(content)
    return "local", None


def read(attachment):
    if attachment.storage_backend == "neon":
        response = s3_client().get_object(Bucket=attachment.storage_bucket, Key=attachment.key)
        stream = response["Body"]
        try:
            content = stream.read(8 * 1024 * 1024 + 1)
        finally:
            stream.close()
    elif attachment.storage_backend == "local":
        content = (Path(current_app.config["STORAGE_PATH"]) / attachment.key).read_bytes()
    else:
        raise RuntimeError("Unknown stored evidence backend")
    if len(content) != attachment.size or hashlib.sha256(content).hexdigest() != attachment.checksum:
        raise ValueError("Private evidence checksum mismatch")
    return content


def remove(key, backend, bucket=None):
    if backend == "neon":
        s3_client().delete_object(Bucket=bucket, Key=key)
    else:
        (Path(current_app.config["STORAGE_PATH"]) / key).unlink(missing_ok=True)
