Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$activateScript = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    . $activateScript
}

python "scripts\launcher.py"
