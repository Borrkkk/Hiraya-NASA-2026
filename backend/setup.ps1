[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        $systemPython = (Get-Command python -ErrorAction Stop).Source
        & $systemPython -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ is required"'
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11 or newer, then run setup.cmd again.' }
        & $systemPython -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    }
    & $python -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the output above and retry.' }
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.env'))) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot '.env.example') -Destination (Join-Path $PSScriptRoot '.env')
    }
    Write-Host 'Setup complete. Put your optional API key in backend/.env.'
    Write-Host 'Start the backend with .\backend\run.cmd from the project root.'
    Write-Host 'For a fast demo on another machine, also copy backend/.cache and backend/.data. See backend/QUICKSTART.md.'
}
finally { Pop-Location }
