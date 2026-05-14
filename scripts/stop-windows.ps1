$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
docker compose down
Write-Host "Prelegal stopped."
