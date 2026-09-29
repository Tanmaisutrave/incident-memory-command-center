# Setup script for Incident Memory Agent
# Uses Read-Host -AsSecureString so keys are not echoed.
# Writes .env values with exact string-literal line replacement (no regex).

#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Incident Memory Agent - Environment Setup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPath    = Join-Path $scriptRoot "..\backend\.env"
$envPath    = [System.IO.Path]::GetFullPath($envPath)
$examplePath = Join-Path $scriptRoot "..\backend\.env.example"
$examplePath = [System.IO.Path]::GetFullPath($examplePath)

# ------------------------------------------------------------------
# Create / overwrite .env from template
# ------------------------------------------------------------------
if (Test-Path $envPath) {
    Write-Host "[!] .env already exists at $envPath" -ForegroundColor Yellow
    $overwrite = (Read-Host "Overwrite it? (y/N)").Trim().ToLower()
    if ($overwrite -eq 'y') {
        Copy-Item $examplePath $envPath -Force
        Write-Host "[+] Created new .env from template" -ForegroundColor Green
    } else {
        Write-Host "[*] Keeping existing .env" -ForegroundColor Green
    }
} else {
    Copy-Item $examplePath $envPath
    Write-Host "[+] Created .env from template" -ForegroundColor Green
}

Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "  API Keys Configuration" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""
Write-Host "You need two API keys (input is hidden):" -ForegroundColor White
Write-Host "  1. Hindsight API Key  — https://hindsight.vectorize.io/" -ForegroundColor Yellow
Write-Host "  2. Groq API Key       — https://console.groq.com/" -ForegroundColor Yellow
Write-Host ""

$configure = (Read-Host "Configure API keys now? (Y/n)").Trim().ToLower()
if ($configure -ne 'n') {

    # Read secrets without echoing them to the terminal
    $hindsightSecure = Read-Host "Hindsight API Key" -AsSecureString
    $groqSecure      = Read-Host "Groq API Key"      -AsSecureString

    # Convert SecureString -> plain text (never written to disk except into .env)
    function ConvertFrom-SecureStringPlain([System.Security.SecureString]$s) {
        $ptr = [System.Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($s)
        try   { return [System.Runtime.InteropServices.Marshal]::PtrToStringUni($ptr) }
        finally { [System.Runtime.InteropServices.Marshal]::ZeroFreeGlobalAllocUnicode($ptr) }
    }

    $hindsightKey = ConvertFrom-SecureStringPlain $hindsightSecure
    $groqKey      = ConvertFrom-SecureStringPlain $groqSecure

    if ($hindsightKey -and $groqKey) {
        # Read current lines and replace the exact placeholder lines.
        # String-literal replacement — no regex, no accidental mismatches.
        $lines = [System.IO.File]::ReadAllLines($envPath)
        $out   = [System.Collections.Generic.List[string]]::new()

        foreach ($line in $lines) {
            if ($line.StartsWith("HINDSIGHT_API_KEY=your_hindsight_api_key_here")) {
                $out.Add("HINDSIGHT_API_KEY=$hindsightKey")
            } elseif ($line.StartsWith("GROQ_API_KEY=your_groq_api_key_here")) {
                $out.Add("GROQ_API_KEY=$groqKey")
            } else {
                $out.Add($line)
            }
        }

        [System.IO.File]::WriteAllLines($envPath, $out)
        Write-Host ""
        Write-Host "[+] API keys written to .env" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "[!] One or both keys were empty — skipped. Edit backend\.env manually." -ForegroundColor Yellow
    }

    # Offer to generate an APP_API_KEY for non-development deployments
    Write-Host ""
    $genKey = (Read-Host "Generate a random APP_API_KEY for production use? (y/N)").Trim().ToLower()
    if ($genKey -eq 'y') {
        $randomKey = -join ((48..57) + (97..102) | Get-Random -Count 64 | ForEach-Object { [char]$_ })
        $lines2 = [System.IO.File]::ReadAllLines($envPath)
        $out2   = [System.Collections.Generic.List[string]]::new()
        foreach ($line in $lines2) {
            if ($line -eq "APP_API_KEY=") {
                $out2.Add("APP_API_KEY=$randomKey")
            } else {
                $out2.Add($line)
            }
        }
        [System.IO.File]::WriteAllLines($envPath, $out2)
        Write-Host "[+] APP_API_KEY written to .env" -ForegroundColor Green
        Write-Host "    Share this key with API consumers; keep it out of source control." -ForegroundColor Gray
    }
} else {
    Write-Host ""
    Write-Host "[*] Edit backend\.env manually to add your API keys." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "  Next Steps" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Verify keys are set in backend\.env" -ForegroundColor White
Write-Host "2. Activate your virtual environment:" -ForegroundColor White
Write-Host "   cd backend" -ForegroundColor Gray
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Run the Hindsight integration test:" -ForegroundColor White
Write-Host "   py ..\scripts\test_hindsight.py" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
