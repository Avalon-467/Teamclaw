Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Resolve-UvPath {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) {
        if ($cmd.Path) {
            return $cmd.Path
        }

        if ($cmd.Source -and (Test-Path $cmd.Source)) {
            return $cmd.Source
        }
    }

    $fallback = Join-Path $HOME ".local\bin\uv.exe"
    if (Test-Path $fallback) {
        return $fallback
    }

    return $null
}

Write-Host "=========================================="
Write-Host "  Mini TimeBot environment setup"
Write-Host "=========================================="
Write-Host ""

$uvPath = Resolve-UvPath
if ($null -ne $uvPath) {
    Write-Host "uv detected: $(& $uvPath --version)"
} else {
    Write-Host "uv not found, installing from Astral..."
    Invoke-RestMethod "https://astral.sh/uv/install.ps1" | Invoke-Expression

    $uvBin = Join-Path $HOME ".local\bin"
    if (Test-Path $uvBin) {
        $env:Path = "$uvBin;$env:Path"
    }

    $uvPath = Resolve-UvPath
    if ($null -eq $uvPath) {
        throw "uv install failed. Please install uv manually: https://docs.astral.sh/uv/"
    }
    Write-Host "uv installed: $(& $uvPath --version)"
}

if (Test-Path ".venv") {
    Write-Host "Virtual environment already exists: .venv/"
} else {
    Write-Host "Creating virtual environment (.venv, Python 3.11+)..."
    & $uvPath venv ".venv" "--python" "3.11"
    Write-Host "Virtual environment created"
}

$activateScript = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $activateScript)) {
    throw "Activation script not found: $activateScript"
}

. $activateScript
Write-Host "Virtual environment activated: $(python --version)"

Write-Host "Installing dependencies (config/requirements.txt)..."
& $uvPath pip install "-r" "config\requirements.txt"
Write-Host "Dependencies installed"

Write-Host ""
Write-Host "--- Config check ---"

if (Test-Path "config/.env") {
    Write-Host "config/.env found"
} else {
    Write-Host "config/.env missing. Run scripts\setup_apikey.ps1 or create it from config\.env.example."
}

if (Test-Path "config/users.json") {
    Write-Host "config/users.json found"
} else {
    Write-Host "config/users.json missing. Run scripts\adduser.ps1 to create a user."
}

Write-Host ""
Write-Host "=========================================="
Write-Host "  Environment setup complete"
Write-Host "  Start services with: scripts\start.ps1"
Write-Host "=========================================="
