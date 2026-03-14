[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Command = "help",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
. (Join-Path $projectRoot "scripts\common.ps1")

Set-TeamClawUtf8

$pidFile = Join-Path $projectRoot ".mini_timebot.pid"
$tunnelPidFile = Join-Path $projectRoot ".tunnel.pid"
$envPath = Join-Path $projectRoot "config\.env"

function Invoke-TeamClawPython {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $python = Ensure-VenvPython -ProjectRoot $projectRoot
    Push-Location $projectRoot
    try {
        & $python @Arguments
        return $LASTEXITCODE
    } finally {
        Pop-Location
    }
}

function Get-EnvValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Key,
        [string]$DefaultValue = ""
    )

    $envValues = Read-TeamClawEnvFile -Path $envPath
    if ($envValues.ContainsKey($Key) -and -not [string]::IsNullOrWhiteSpace($envValues[$Key])) {
        return $envValues[$Key]
    }

    return $DefaultValue
}

function Show-Help {
    Write-Host "TeamClaw Windows PowerShell entry point"
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File selfskill\scripts\run.ps1 <command> [args]"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  setup                          Install or update Python dependencies"
    Write-Host "  start                          Start services in the background"
    Write-Host "  stop                           Stop services"
    Write-Host "  status                         Show current service status"
    Write-Host "  add-user <name> <password>     Create or update a password user"
    Write-Host "  configure ...                  Run selfskill/scripts/configure.py"
    Write-Host "  auto-model                     Query available models from the configured API"
    Write-Host "  cli ...                        Run scripts/cli.py"
    Write-Host "  check-openclaw                 Detect or install OpenClaw"
    Write-Host "  start-tunnel                   Start Cloudflare Tunnel in the background"
    Write-Host "  stop-tunnel                    Stop Cloudflare Tunnel"
    Write-Host "  tunnel-status                  Show Cloudflare Tunnel status"
    Write-Host "  help                           Show this help"
}

function Show-PortChecks {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Checks,
        [Parameter(Mandatory = $true)]
        [hashtable]$Ports
    )

    foreach ($entry in $Ports.GetEnumerator()) {
        $check = $Checks[$entry.Key]
        if ($check.Available) {
            Write-Host "  $($entry.Key)=$($entry.Value) is available"
        } else {
            Write-Host "  $($entry.Key)=$($entry.Value) is blocked: $([string]::Join('; ', $check.Reasons))"
        }
    }
}

function Prepare-TeamClawPorts {
    $resolution = Resolve-TeamClawPortConfiguration -EnvPath $envPath

    if ($resolution.AutoUpdated) {
        Write-Host "The default TeamClaw ports are blocked on this Windows machine."
        Write-Host "Updated config/.env to use a safe local port set:"
        foreach ($entry in $resolution.NewPorts.GetEnumerator()) {
            Write-Host "  $($entry.Key): $($resolution.CurrentPorts[$entry.Key]) -> $($entry.Value)"
        }
    } elseif ($resolution.RequiresManualUpdate) {
        Write-Host "The configured TeamClaw ports are blocked and were not auto-changed because they are custom values."
        Show-PortChecks -Checks $resolution.Checks -Ports $resolution.CurrentPorts
        Write-Host "Update PORT_AGENT / PORT_SCHEDULER / PORT_OASIS / PORT_FRONTEND in config/.env, then try again."
        return $null
    }

    return Get-TeamClawPortMap -EnvPath $envPath
}

function Show-StartupFailureDiagnostics {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StdOutLog,
        [Parameter(Mandatory = $true)]
        [string]$StdErrLog
    )

    $stderrTail = Get-TeamClawLogTail -Path $StdErrLog -LineCount 25
    if ($stderrTail.Count -gt 0) {
        Write-Host ""
        Write-Host "Last stderr lines:"
        foreach ($line in $stderrTail) {
            Write-Host "  $line"
        }
    }

    $stdoutTail = Get-TeamClawLogTail -Path $StdOutLog -LineCount 15
    if ($stdoutTail.Count -gt 0) {
        Write-Host ""
        Write-Host "Last stdout lines:"
        foreach ($line in $stdoutTail) {
            Write-Host "  $line"
        }
    }
}

switch ($Command) {
    "setup" {
        & (Join-Path $projectRoot "scripts\setup_env.ps1")
        exit $LASTEXITCODE
    }

    "start" {
        if (-not (Test-Path $envPath)) {
            Write-Host "config/.env is missing. Run:"
            Write-Host "  powershell -ExecutionPolicy Bypass -File .\selfskill\scripts\run.ps1 configure --init"
            exit 1
        }

        $ports = Prepare-TeamClawPorts
        if (-not $ports) {
            exit 1
        }

        if (Test-TrackedProcessRunning -PidFile $pidFile) {
            $oldPid = Get-TrackedProcessId -PidFile $pidFile
            Write-Host "Found an existing instance (PID: $oldPid). Stopping it first..."
            Stop-TrackedProcess -PidFile $pidFile | Out-Null
        } else {
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        }

        $python = Ensure-VenvPython -ProjectRoot $projectRoot
        $env:MINI_TIMEBOT_HEADLESS = "1"
        $stdoutLog = Join-Path $projectRoot "logs\launcher.out.log"
        $stderrLog = Join-Path $projectRoot "logs\launcher.err.log"
        $process = Start-BackgroundPythonProcess `
            -ProjectRoot $projectRoot `
            -PythonPath $python `
            -Arguments @("scripts\launcher.py") `
            -StdOutLog $stdoutLog `
            -StdErrLog $stderrLog

        Set-Content -Path $pidFile -Value $process.Id -Encoding UTF8
        $agentPort = [int]$ports["PORT_AGENT"]
        $frontendPort = [int]$ports["PORT_FRONTEND"]

        Write-Host "Service started. PID: $($process.Id)"
        Write-Host "Logs:"
        Write-Host "  stdout: $stdoutLog"
        Write-Host "  stderr: $stderrLog"
        Write-Host "Waiting for http://127.0.0.1:$agentPort/v1/models ..."

        if (Wait-HttpEndpoint -Url "http://127.0.0.1:$agentPort/v1/models") {
            Write-Host "Service is ready."
            Write-Host "Web UI: http://127.0.0.1:$frontendPort"
            exit 0
        }

        Start-Sleep -Seconds 1
        if (-not (Test-TrackedProcessRunning -PidFile $pidFile)) {
            Write-Host "Service exited during startup."
            Show-StartupFailureDiagnostics -StdOutLog $stdoutLog -StdErrLog $stderrLog
            exit 1
        }

        Write-Host "Service is still starting. Check status or logs if it does not become ready soon."
        Write-Host "Web UI (when ready): http://127.0.0.1:$frontendPort"
        exit 0
    }

    "stop" {
        if (Stop-TrackedProcess -PidFile $pidFile) {
            Write-Host "Service stopped."
        } else {
            Write-Host "Service is not running."
        }
        exit 0
    }

    "status" {
        $ports = Get-TeamClawPortMap -EnvPath $envPath

        if (-not (Test-TrackedProcessRunning -PidFile $pidFile)) {
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
            Write-Host "Service is not running."
            if (Test-Path $envPath) {
                $checks = @{}
                foreach ($entry in $ports.GetEnumerator()) {
                    $checks[$entry.Key] = Test-TeamClawPortAvailability -Port $entry.Value
                }
                Show-PortChecks -Checks $checks -Ports $ports
            }
            exit 1
        }

        $pidValue = Get-TrackedProcessId -PidFile $pidFile
        Write-Host "Service is running. PID: $pidValue"

        foreach ($entry in $ports.GetEnumerator()) {
            $listener = Get-ListeningPortInfo -Port $entry.Value
            if ($listener) {
                Write-Host "  $($entry.Key)=$($entry.Value) is listening (PID $($listener.OwningProcess))"
            } else {
                $check = Test-TeamClawPortAvailability -Port $entry.Value
                if ($check.Available) {
                    Write-Host "  $($entry.Key)=$($entry.Value) is not listening yet"
                } else {
                    Write-Host "  $($entry.Key)=$($entry.Value) is blocked: $([string]::Join('; ', $check.Reasons))"
                }
            }
        }

        exit 0
    }

    "add-user" {
        if ($Rest.Count -lt 2) {
            Write-Host "Usage: run.ps1 add-user <username> <password>"
            exit 1
        }

        $code = Invoke-TeamClawPython -Arguments @("selfskill\scripts\adduser.py", $Rest[0], $Rest[1])
        exit $code
    }

    "configure" {
        if ($Rest.Count -eq 0) {
            Write-Host "Usage: run.ps1 configure <KEY> <VALUE> | --init | --show | --batch ..."
            exit 1
        }

        $code = Invoke-TeamClawPython -Arguments (@("selfskill\scripts\configure.py") + $Rest)
        exit $code
    }

    "auto-model" {
        $code = Invoke-TeamClawPython -Arguments @("selfskill\scripts\configure.py", "--auto-model")
        exit $code
    }

    "cli" {
        if ($Rest.Count -eq 0) {
            Write-Host "Usage: run.ps1 cli <command> [args]"
            exit 1
        }

        $code = Invoke-TeamClawPython -Arguments (@("scripts\cli.py") + $Rest)
        exit $code
    }

    "check-openclaw" {
        $python = Ensure-VenvPython -ProjectRoot $projectRoot
        $openclaw = Get-Command openclaw -ErrorAction SilentlyContinue
        if ($openclaw) {
            Write-Host "OpenClaw detected at: $($openclaw.Source)"
            $code = Invoke-TeamClawPython -Arguments @("selfskill\scripts\configure_openclaw.py", "--auto-detect")
            exit $code
        }

        $node = Get-Command node -ErrorAction SilentlyContinue
        $npm = Get-Command npm -ErrorAction SilentlyContinue
        if (-not $node -or -not $npm) {
            Write-Host "node/npm were not found."
            Write-Host "On native Windows, install Node.js 22+ first, or use the WSL flow documented in SKILL.md."
            exit 1
        }

        $nodeVersion = (& $node.Source --version).Trim()
        $nodeMajor = [int]($nodeVersion.TrimStart("v").Split(".")[0])
        if ($nodeMajor -lt 22) {
            Write-Host "Node.js is too old: $nodeVersion"
            Write-Host "Please upgrade to Node.js 22+ or use the WSL flow."
            exit 1
        }

        $shouldInstall = $env:OPENCLAW_AUTO_INSTALL -eq "1"
        if (-not $shouldInstall) {
            $reply = Read-Host "OpenClaw is missing. Install it now? [y/N]"
            $shouldInstall = $reply -match "^[Yy]"
        }

        if (-not $shouldInstall) {
            Write-Host "Skipped OpenClaw installation."
            exit 0
        }

        & $npm.Source install -g openclaw@latest --ignore-scripts
        if ($LASTEXITCODE -ne 0) {
            throw "OpenClaw installation failed. Check npm and your network connection."
        }

        & $python "selfskill\scripts\configure_openclaw.py" "--init-workspace"
        if ($LASTEXITCODE -ne 0) {
            throw "OpenClaw workspace initialization failed."
        }

        Write-Host "OpenClaw has been installed."
        Write-Host "Next, run:"
        Write-Host "  openclaw onboard --install-daemon"
        Write-Host "Then run:"
        Write-Host "  powershell -ExecutionPolicy Bypass -File .\selfskill\scripts\run.ps1 check-openclaw"
        exit 0
    }

    "start-tunnel" {
        if (Test-TrackedProcessRunning -PidFile $tunnelPidFile) {
            $existingPid = Get-TrackedProcessId -PidFile $tunnelPidFile
            Write-Host "Tunnel is already running. PID: $existingPid"
            exit 0
        }

        $python = Ensure-VenvPython -ProjectRoot $projectRoot
        $stdoutLog = Join-Path $projectRoot "logs\tunnel.out.log"
        $stderrLog = Join-Path $projectRoot "logs\tunnel.err.log"
        $process = Start-BackgroundPythonProcess `
            -ProjectRoot $projectRoot `
            -PythonPath $python `
            -Arguments @("scripts\tunnel.py") `
            -StdOutLog $stdoutLog `
            -StdErrLog $stderrLog

        Set-Content -Path $tunnelPidFile -Value $process.Id -Encoding UTF8
        Write-Host "Tunnel started. PID: $($process.Id)"
        Write-Host "Logs:"
        Write-Host "  stdout: $stdoutLog"
        Write-Host "  stderr: $stderrLog"
        exit 0
    }

    "stop-tunnel" {
        if (Stop-TrackedProcess -PidFile $tunnelPidFile) {
            Write-Host "Tunnel stopped."
        } else {
            Write-Host "Tunnel is not running."
        }
        exit 0
    }

    "tunnel-status" {
        if (-not (Test-TrackedProcessRunning -PidFile $tunnelPidFile)) {
            Write-Host "Tunnel is not running."
            exit 1
        }

        $pidValue = Get-TrackedProcessId -PidFile $tunnelPidFile
        Write-Host "Tunnel is running. PID: $pidValue"

        $envValues = Read-TeamClawEnvFile -Path $envPath
        if ($envValues.ContainsKey("PUBLIC_DOMAIN") -and -not [string]::IsNullOrWhiteSpace($envValues["PUBLIC_DOMAIN"])) {
            Write-Host "Public URL: $($envValues["PUBLIC_DOMAIN"])"
        }

        exit 0
    }

    "help" { Show-Help; exit 0 }
    "--help" { Show-Help; exit 0 }
    "-h" { Show-Help; exit 0 }

    default {
        Write-Host "Unknown command: $Command"
        Show-Help
        exit 1
    }
}
