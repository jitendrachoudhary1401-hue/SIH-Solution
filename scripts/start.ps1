param([switch]$Worker)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) { throw 'Create .venv and install backend requirements first. See README.md.' }
if ($Worker) { & '.venv/Scripts/python.exe' 'backend/worker.py' }
else { & '.venv/Scripts/python.exe' 'backend/serve.py' }
