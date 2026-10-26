"""Explicit network setup; inference itself is strictly local. Saves resolved model SHAs."""
import json
import os
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

runtime = Path(__file__).resolve().parent / ".runtime"
legacy_runtime = Path(__file__).resolve().parents[1] / ".runtime"
if os.getenv("APP_ENV", "development") != "production" and legacy_runtime.exists():
    runtime = legacy_runtime
root = Path(os.getenv("MODEL_PATH", str(runtime / "models")))
root.mkdir(parents=True, exist_ok=True)
manifest = {}
for kind, repo in [("embedding", "sentence-transformers/all-MiniLM-L6-v2"), ("reranker", "cross-encoder/ms-marco-MiniLM-L6-v2")]:
    revision = HfApi().model_info(repo).sha
    snapshot_download(repo, revision=revision, local_dir=root / kind,
                      allow_patterns=["*.json", "*.txt", "*.safetensors", "*.model", "*.vocab"])
    manifest[kind] = {"model": repo, "revision": revision}
(root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print("Pinned local model bundle saved to", root)
