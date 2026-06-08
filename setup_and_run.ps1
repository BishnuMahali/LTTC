# Sarvam Timed Captions (STC) - One-Click Setup & Launch Script
try {
    $ErrorActionPreference = "Stop"
    Set-Location $PSScriptRoot

    Clear-Host
    Write-Host "====================================================" -ForegroundColor Cyan
    Write-Host "         Sarvam Timed Captions Dashboard" -ForegroundColor Cyan
    Write-Host "====================================================" -ForegroundColor Cyan
    Write-Host ""

    # 1. Check Python
    Write-Host "Checking Python..." -ForegroundColor Gray
    if (!(Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: Python is not installed." -ForegroundColor Red
        Write-Host "Please install Python 3.10 or newer from https://www.python.org/" -ForegroundColor Yellow
        Write-Host "IMPORTANT: Make sure to check 'Add Python to PATH' during installation." -ForegroundColor White
        throw "Python Missing"
    }

    # 2. Manage Virtual Environment
    $venvPath = Join-Path $PSScriptRoot ".venv"
    if (!(Test-Path $venvPath)) {
        Write-Host "[1/2] Creating isolated environment (first-time setup)..." -ForegroundColor Green
        python -m venv .venv
    }

    # Activate venv
    $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        Write-Host "Activating environment..." -ForegroundColor Gray
        . $activateScript
    } else {
        Write-Host "ERROR: Environment folder exists but is broken." -ForegroundColor Red
        Write-Host "Please delete the '.venv' folder and try again." -ForegroundColor Yellow
        throw "VENV Broken"
    }

    # 3. Handle Local AI Engine (Only if needed)
    $torchStatus = python -c "import importlib.util; print('OK' if importlib.util.find_spec('torch') else 'MISSING')"
    if ($torchStatus -and $torchStatus.ToString().Trim() -eq "MISSING") {
        Write-Host ""
        Write-Host "Local AI Engine (PyTorch) needs setup for Whisper mode." -ForegroundColor Yellow
        $gpuResponse = Read-Host "Do you have an NVIDIA GPU? (y/n)"
        if ($gpuResponse -match "^[yY]") {
            Write-Host "Installing GPU version (~2GB download)..." -ForegroundColor Cyan
            python -m pip install torch==2.3.0 torchaudio==2.3.0 torchvision==0.18.0 --index-url https://download.pytorch.org/whl/cu118
        } else {
            Write-Host "Installing CPU version..." -ForegroundColor Cyan
            python -m pip install torch==2.3.0 torchaudio==2.3.0 torchvision==0.18.0 --index-url https://download.pytorch.org/whl/cpu
        }
    }

    # 4. Ensure other packages
    Write-Host "[2/2] Checking app components..." -ForegroundColor Green
    python -m pip install -r requirements.txt --quiet
    python -m pip install -e . --quiet

    # 5. Check FFmpeg
    Write-Host "Checking FFmpeg..." -ForegroundColor Gray
    if (!(Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        Write-Host "WARNING: FFmpeg not found. Please install FFmpeg and add to PATH." -ForegroundColor Yellow
    }

    # 6. Launch
    Write-Host "Starting Dashboard..." -ForegroundColor Green
    python SRC/STC.py
    if ($LASTEXITCODE -ne 0) {
        throw "Application crashed with exit code $LASTEXITCODE."
    }
}
catch {
    Write-Host ""
    Write-Host "!!! CRITICAL ERROR !!!" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}
