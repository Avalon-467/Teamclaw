[CmdletBinding()]
param(
    [string]$PythonVersion = "3.11"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "common.ps1")

Set-TeamClawUtf8
Push-Location $projectRoot

try {
    Write-Host "=========================================="
    Write-Host "  TeamClaw Windows environment setup"
    Write-Host "=========================================="
    Write-Host ""

    $uv = Ensure-UvInstalled
    Write-Host "Detected uv at: $uv"

    $venvPython = Get-VenvPython -ProjectRoot $projectRoot
    if (-not $venvPython) {
        Write-Host "Creating .venv with Python $PythonVersion ..."
        & $uv venv .venv --python $PythonVersion
        if ($LASTEXITCODE -ne 0) {
            Write-Host "uv venv failed on the first attempt. Trying to install Python $PythonVersion via uv ..."
            & $uv python install $PythonVersion
            if ($LASTEXITCODE -ne 0) {
                throw "uv python install failed. Verify your network connection or install Python manually."
            }

            & $uv venv .venv --python $PythonVersion
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to create .venv."
            }
        }

        $venvPython = Ensure-VenvPython -ProjectRoot $projectRoot
        Write-Host "Created virtual environment: $venvPython"
    } else {
        Write-Host "Virtual environment already exists: $venvPython"
    }

    Write-Host "Installing or updating Python dependencies ..."
    & $uv pip install -r config\requirements.txt --python $venvPython
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed."
    }

    Write-Host ""
    if (Test-Path "config\.env") {
        Write-Host "config/.env already exists"
    } else {
        Write-Host "config/.env is missing. Initialize it with:"
        Write-Host "  powershell -ExecutionPolicy Bypass -File .\selfskill\scripts\run.ps1 configure --init"
    }

    if (Test-Path "config\users.json") {
        Write-Host "config/users.json already exists"
    } else {
        Write-Host "config/users.json is missing. If you need password login, run:"
        Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\adduser.ps1"
    }

    Write-Host ""
    Write-Host "Environment setup completed."
} finally {
    Pop-Location
}
