# Setup script for Incident Memory Agent
# This script helps you configure the environment

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Incident Memory Agent - Environment Setup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
$envPath = "backend\.env"
if (Test-Path $envPath) {
    Write-Host "[!] .env file already exists at backend\.env" -ForegroundColor Yellow
    $overwrite = Read-Host "Do you want to overwrite it? (y/N)"
    if ($overwrite -ne "y") {
        Write-Host "[*] Keeping existing .env file" -ForegroundColor Green
    } else {
        Copy-Item "backend\.env.example" $envPath -Force
        Write-Host "[+] Created new .env file from template" -ForegroundColor Green
    }
} else {
    Copy-Item "backend\.env.example" $envPath
    Write-Host "[+] Created .env file from template" -ForegroundColor Green
}

Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "  API Keys Configuration" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""

Write-Host "You need two API keys:" -ForegroundColor White
Write-Host ""
Write-Host "1. Hindsight API Key" -ForegroundColor Yellow
Write-Host "   Get it from: https://hindsight.vectorize.io/" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Groq API Key" -ForegroundColor Yellow
Write-Host "   Get it from: https://console.groq.com/" -ForegroundColor Gray
Write-Host ""

$configureNow = Read-Host "Do you want to configure API keys now? (Y/n)"

if ($configureNow -ne "n") {
    Write-Host ""
    $hindsightKey = Read-Host "Enter your Hindsight API Key"
    $groqKey = Read-Host "Enter your Groq API Key"
    
    if ($hindsightKey -and $groqKey) {
        # Read the .env file
        $envContent = Get-Content $envPath
        
        # Replace the placeholder values
        $envContent = $envContent -replace 'HINDSIGHT_API_KEY=.*', "HINDSIGHT_API_KEY=$hindsightKey"
        $envContent = $envContent -replace 'GROQ_API_KEY=.*', "GROQ_API_KEY=$groqKey"
        
        # Write back
        $envContent | Set-Content $envPath
        
        Write-Host ""
        Write-Host "[+] API keys configured successfully!" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "[!] API keys not provided. Please edit backend\.env manually" -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "[*] Please edit backend\.env and add your API keys manually" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "  Next Steps" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Ensure API keys are configured in backend\.env" -ForegroundColor White
Write-Host "2. Activate the virtual environment:" -ForegroundColor White
Write-Host "   cd backend" -ForegroundColor Gray
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Run the Hindsight integration test:" -ForegroundColor White
Write-Host "   py ..\scripts\test_hindsight.py" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
