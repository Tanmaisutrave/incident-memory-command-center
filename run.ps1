param([switch]$Rebuild)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'First run the setup steps in README.md to create .venv.' }
if ($Rebuild -or -not (Test-Path -LiteralPath 'frontend\dist\index.html')) {
    Push-Location frontend
    try { & npm.cmd run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' } } finally { Pop-Location }
}
Write-Host 'Open http://127.0.0.1:8000. Press Ctrl+C here to stop.'
& $pythonPath -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
