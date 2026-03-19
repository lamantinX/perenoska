$ErrorActionPreference = "Stop"

$runId = Get-Date -Format "yyyyMMdd-HHmmss-fff"
$pytestBaseTemp = Join-Path $env:LOCALAPPDATA "Temp\\perenoska-pytest-$runId"
$pytestCacheDir = Join-Path $env:LOCALAPPDATA "Temp\\perenoska-pytest-cache-$runId"

New-Item -ItemType Directory -Force -Path $pytestBaseTemp | Out-Null
New-Item -ItemType Directory -Force -Path $pytestCacheDir | Out-Null

Write-Host "Running pytest..."
python -m pytest --basetemp=$pytestBaseTemp -o cache_dir=$pytestCacheDir

Write-Host "Checking git remote..."
git remote -v
