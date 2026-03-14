Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$EnvFile = Join-Path $ProjectRoot "config/.env"
$ExampleFile = Join-Path $ProjectRoot "config/.env.example"

function Get-DotEnvValue {
    param(
        [string]$Path,
        [string]$Key
    )

    if (-not (Test-Path $Path)) {
        return $null
    }

    foreach ($line in Get-Content -Path $Path -Encoding UTF8) {
        if ($line -match "^(#\s*)?$([regex]::Escape($Key))=(.*)$") {
            return $matches[2]
        }
    }

    return $null
}

function Set-DotEnvValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Value
    )

    $pattern = "^(#\s*)?$([regex]::Escape($Key))=.*$"
    $replacement = "$Key=$Value"
    $lines = @()

    if (Test-Path $Path) {
        $lines = @(Get-Content -Path $Path -Encoding UTF8)
    }

    $updated = $false
    $newLines = @(
        foreach ($line in $lines) {
        if ($line -match $pattern) {
            $updated = $true
            $replacement
        } else {
            $line
        }
    }
    )

    if (-not $updated) {
        if ($newLines.Count -gt 0 -and $newLines[-1] -ne "") {
            $newLines += ""
        }
        $newLines += $replacement
    }

    Set-Content -Path $Path -Value $newLines -Encoding UTF8
}

$existingKey = Get-DotEnvValue -Path $EnvFile -Key "LLM_API_KEY"
if ($existingKey -and $existingKey -ne "your_api_key_here") {
    if ($existingKey.Length -ge 12) {
        $maskedKey = "{0}...{1}" -f $existingKey.Substring(0, 8), $existingKey.Substring($existingKey.Length - 4)
    } else {
        $maskedKey = "[configured]"
    }

    Write-Host "API Key already configured ($maskedKey)"
    $reset = Read-Host "Reconfigure it? (y/N)"
    if ($reset -notmatch "^[Yy]$") {
        Write-Host "Keeping current configuration"
        exit 0
    }
}

Write-Host "================================================"
Write-Host "  Configure LLM API access"
Write-Host "  Supports DeepSeek / OpenAI / Gemini / Claude"
Write-Host "================================================"
Write-Host ""

$apiKey = Read-Host "Enter API Key"
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    Write-Host "No API Key entered. Skipping configuration."
    exit 1
}

$baseUrl = Read-Host "Enter API Base URL (default https://api.deepseek.com, no /v1)"
if ([string]::IsNullOrWhiteSpace($baseUrl)) {
    $baseUrl = "https://api.deepseek.com"
}

$modelName = Read-Host "Enter model name (default deepseek-chat)"
if ([string]::IsNullOrWhiteSpace($modelName)) {
    $modelName = "deepseek-chat"
}

$ttsModel = Read-Host "Enter TTS model name (default gemini-2.5-flash-preview-tts)"
if ([string]::IsNullOrWhiteSpace($ttsModel)) {
    $ttsModel = "gemini-2.5-flash-preview-tts"
}

$ttsVoice = ""
if (-not [string]::IsNullOrWhiteSpace($ttsModel)) {
    $ttsVoice = Read-Host "Enter TTS voice (default charon)"
    if ([string]::IsNullOrWhiteSpace($ttsVoice)) {
        $ttsVoice = "charon"
    }
}

$visionInput = Read-Host "Does this model support vision/image input? (y/N)"
$visionSupport = if ($visionInput -match "^[Yy]$") { "true" } else { "false" }

$standardInput = Read-Host "Use OpenAI standard API mode? (Y/n)"
$standardMode = if ($standardInput -match "^[Nn]$") { "false" } else { "true" }

if (-not (Test-Path $EnvFile) -and (Test-Path $ExampleFile)) {
    Copy-Item $ExampleFile $EnvFile
}

Set-DotEnvValue -Path $EnvFile -Key "LLM_API_KEY" -Value $apiKey
Set-DotEnvValue -Path $EnvFile -Key "LLM_BASE_URL" -Value $baseUrl
Set-DotEnvValue -Path $EnvFile -Key "LLM_MODEL" -Value $modelName
Set-DotEnvValue -Path $EnvFile -Key "TTS_MODEL" -Value $ttsModel
Set-DotEnvValue -Path $EnvFile -Key "TTS_VOICE" -Value $ttsVoice
Set-DotEnvValue -Path $EnvFile -Key "LLM_VISION_SUPPORT" -Value $visionSupport
Set-DotEnvValue -Path $EnvFile -Key "OPENAI_STANDARD_MODE" -Value $standardMode

Write-Host "API configuration saved to config/.env"
