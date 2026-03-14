Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot
$env:MINI_TIMEBOT_HEADLESS = "0"

function Stop-TeamClawProcesses {
    $patterns = @(
        "scripts\\launcher.py",
        "src\\time.py",
        "oasis\\server.py",
        "src\\mainagent.py",
        "src\\front.py"
    )

    $procs = Get-CimInstance Win32_Process | Where-Object {
        $cmd = $_.CommandLine
        if ([string]::IsNullOrWhiteSpace($cmd)) {
            return $false
        }

        foreach ($pattern in $patterns) {
            if ($cmd -match [regex]::Escape($pattern)) {
                return $true
            }
        }

        return $false
    }

    foreach ($proc in $procs) {
        Write-Host "Cleaning old process PID $($proc.ProcessId): $($proc.CommandLine)"
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "========== 1/4 Environment setup =========="
& (Join-Path $ProjectRoot "scripts\setup_env.ps1")

$activateScript = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    . $activateScript
}

Write-Host ""
Write-Host "========== 2/4 API Key setup =========="
try {
    & (Join-Path $ProjectRoot "scripts\setup_apikey.ps1")
} catch {
    Write-Warning "API Key setup did not finish: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "========== 3/4 User management =========="
$addUser = Read-Host "Add a new user? (y/N)"
if ($addUser -match "^[Yy]$") {
    & (Join-Path $ProjectRoot "scripts\adduser.ps1")
}

Write-Host ""
Write-Host "========== 4/4 Start services =========="
Stop-TeamClawProcesses

$tunnelProc = $null
$useTunnel = Read-Host "Deploy to public network? (y/N)"
if ($useTunnel -match "^[Yy]$") {
    Write-Host "Starting Cloudflare Tunnel in background..."
    $tunnelProc = Start-Process -FilePath "python" -ArgumentList "scripts/tunnel.py" -WorkingDirectory $ProjectRoot -PassThru
    Start-Sleep -Seconds 2
}

try {
    python "scripts\launcher.py"
} finally {
    if ($null -ne $tunnelProc -and -not $tunnelProc.HasExited) {
        Stop-Process -Id $tunnelProc.Id -Force -ErrorAction SilentlyContinue
    }
}
