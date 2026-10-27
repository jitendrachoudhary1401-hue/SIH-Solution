"""Explicit network setup; inference itself is strictly local. Saves resolved model SHAs."""
import json
import os
from pathlib import Path
from huggingface_hub import snapshot_download

runtime = Path(__file__).resolve().parent / ".runtime"
legacy_runtime = Path(__file__).resolve().parents[1] / ".runtime"
if os.getenv("APP_ENV", "development") != "production" and legacy_runtime.exists():
    runtime = legacy_runtime
root = Path(os.getenv("MODEL_PATH", str(runtime / "models")))
if (os.getenv("APP_ENV", "development") != "production" and not (root / "manifest.json").exists()
        and (runtime / "models" / "manifest.json").exists()):
    root = runtime / "models"
root.mkdir(parents=True, exist_ok=True)
manifest = json.loads((Path(__file__).resolve().parent / "model-bundle.json").read_text(encoding="utf-8"))
for kind, model in manifest.items():
    repo, revision = model["model"], model["revision"]
    snapshot_download(repo, revision=revision, local_dir=root / kind,
                      allow_patterns=["*.json", "*.txt", "*.safetensors", "*.model", "*.vocab"])
(root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print("Pinned local model bundle saved to", root)
