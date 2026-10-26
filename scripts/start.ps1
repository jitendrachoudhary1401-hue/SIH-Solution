param([switch]$Worker)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) { throw 'Create .venv and install backend requirements first. See README.md.' }
if ($Worker) { & '.venv/Scripts/python.exe' 'backend/worker.py' }
else { & '.venv/Scripts/waitress-serve.exe' '--host=127.0.0.1' '--port=5000' '--call' 'backend.app:create_app' }
