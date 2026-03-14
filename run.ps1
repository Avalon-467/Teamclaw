[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
. (Join-Path $projectRoot "scripts\common.ps1")

Set-TeamClawUtf8
$runScript = Join-Path $projectRoot "selfskill\scripts\run.ps1"
$envPath = Join-Path $projectRoot "config\.env"

Write-Host "========== 1/4 Environment setup =========="
& (Join-Path $projectRoot "scripts\setup_env.ps1")

if (-not (Test-Path $envPath)) {
    Write-Host ""
    Write-Host "Initializing config/.env ..."
    & $runScript configure --init
}

$envValues = Read-TeamClawEnvFile -Path $envPath
$apiKeyConfigured = $envValues.ContainsKey("LLM_API_KEY") -and `
    -not [string]::IsNullOrWhiteSpace($envValues["LLM_API_KEY"]) -and `
    $envValues["LLM_API_KEY"] -ne "your_api_key_here"

if (-not $apiKeyConfigured) {
    Write-Host ""
    Write-Host "========== 2/4 API Key setup =========="
    & (Join-Path $projectRoot "scripts\setup_apikey.ps1")
} else {
    Write-Host ""
    Write-Host "========== 2/4 API Key setup =========="
    Write-Host "LLM API configuration already exists."
}

Write-Host ""
Write-Host "========== 3/4 User management =========="
$addUser = Read-Host "Add a password user now? (y/N)"
if ($addUser -match "^[Yy]$") {
    & (Join-Path $projectRoot "scripts\adduser.ps1")
}

Write-Host ""
Write-Host "========== 4/4 Start services =========="
& $runScript start

$useTunnel = Read-Host "Start Cloudflare Tunnel for public access? (y/N)"
if ($useTunnel -match "^[Yy]$") {
    & $runScript start-tunnel
}
