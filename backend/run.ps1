[CmdletBinding()]
param([string]$IndexDir, [switch]$Check)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'load-config.ps1')
Import-BackendConfig -BackendDir $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Create backend/.venv and install requirements.txt first.'
}
if (-not $IndexDir -and $env:SPHEREX_INDEX_DIR) { $IndexDir = $env:SPHEREX_INDEX_DIR }
if (-not $IndexDir) {
    $snapshot = Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot '.cache\exposure-index') -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'index.json') } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $snapshot) { throw 'No exposure index found. Copy backend/.cache from the demo computer, or install an index. See backend/QUICKSTART.md.' }
    $IndexDir = $snapshot.FullName
}
$IndexDir = (Resolve-Path -LiteralPath $IndexDir).Path
if (-not (Test-Path -LiteralPath (Join-Path $IndexDir 'index.json')) -or
    -not (Test-Path -LiteralPath (Join-Path $IndexDir 'tiles'))) {
    throw 'IndexDir must contain index.json and a tiles directory.'
}
Write-Host 'Configuration loaded from backend/.env (terminal overrides take precedence).'
if ($Check) {
    Write-Host "Index: $IndexDir"
    Write-Host 'Backend startup checks passed.'
    if ($env:OPENAI_API_KEY -and $env:PULSR_AI_MODEL) { Write-Host "AI configured: $env:PULSR_AI_MODEL" }
    else { Write-Host 'AI not configured; data summaries remain available.' }
    return
}
$previousIndex = $env:SPHEREX_INDEX_DIR
$previousSource = $env:SPHEREX_IMAGE_SOURCE
Push-Location -LiteralPath $PSScriptRoot
try {
    $env:SPHEREX_INDEX_DIR = $IndexDir
    if (-not $env:SPHEREX_IMAGE_SOURCE) { $env:SPHEREX_IMAGE_SOURCE = 's3' }
    Write-Host "Exposure index: $IndexDir"
    Write-Host 'Image source: S3. Backend docs: http://localhost:8000/docs'
    & $python -m uvicorn app.main:app --reload --port 8000
    $serverExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
    $env:SPHEREX_INDEX_DIR = $previousIndex
    $env:SPHEREX_IMAGE_SOURCE = $previousSource
}
exit $serverExitCode
