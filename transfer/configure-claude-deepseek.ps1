$ErrorActionPreference = "Stop"

$envFile = Join-Path $env:USERPROFILE "Desktop\ces\env.txt"
if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw "API key file not found: $envFile"
}

$lines = @(Get-Content -LiteralPath $envFile | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith("#") })
$apiKey = $null

foreach ($line in $lines) {
    if ($line -match '^(?:export\s+)?(?:DEEPSEEK_API_KEY|ANTHROPIC_AUTH_TOKEN|API_KEY)\s*=\s*(.+?)\s*$') {
        $apiKey = $Matches[1].Trim().Trim('"').Trim("'")
        break
    }
}

if (-not $apiKey) {
    $rawCandidates = @($lines | ForEach-Object { $_.Trim().Trim('"').Trim("'") } | Where-Object { $_ -match '^[A-Za-z0-9_.-]{20,}$' })
    if ($rawCandidates.Count -eq 1) {
        $apiKey = $rawCandidates[0]
    } elseif ($rawCandidates.Count -gt 1) {
        throw "Multiple possible API keys found in env.txt; keep only the intended DeepSeek key or name it DEEPSEEK_API_KEY."
    }
}

if (-not $apiKey -or $apiKey.Length -lt 20) {
    throw "No valid API key was found in env.txt."
}

$claudeDir = Join-Path $env:USERPROFILE ".claude"
$settingsPath = Join-Path $claudeDir "settings.json"
New-Item -ItemType Directory -Path $claudeDir -Force | Out-Null

if (Test-Path -LiteralPath $settingsPath) {
    $existingSettings = Get-Content -LiteralPath $settingsPath -Raw
    if ($existingSettings -notmatch 'duolaiduo\.psynaut\.cn') {
        $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
        Copy-Item -LiteralPath $settingsPath -Destination "$settingsPath.backup-$timestamp" -Force
    }
}

$settings = [ordered]@{
    env = [ordered]@{
        CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"
        ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"
        ANTHROPIC_AUTH_TOKEN = $apiKey
        ANTHROPIC_MODEL = "deepseek-v4-flash"
        ANTHROPIC_DEFAULT_OPUS_MODEL = "deepseek-v4-flash"
        ANTHROPIC_DEFAULT_SONNET_MODEL = "deepseek-v4-flash"
        ANTHROPIC_DEFAULT_HAIKU_MODEL = "deepseek-v4-flash"
        CLAUDE_CODE_SUBAGENT_MODEL = "deepseek-v4-flash"
        CLAUDE_CODE_EFFORT_LEVEL = "max"
        CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS = "1"
        CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = "1"
        teammateMode = "tmux"
    }
}

$settings | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $settingsPath -Encoding UTF8

$aclUser = $env:USERNAME + ":(F)"
icacls.exe $settingsPath /inheritance:r | Out-Null
icacls.exe $settingsPath /grant:r $aclUser | Out-Null
icacls.exe $settingsPath /grant "*S-1-5-18:(F)" | Out-Null

Write-Host "CONFIGURED=$settingsPath"
Write-Host "BASE_URL=https://api.deepseek.com/anthropic"
Write-Host "MODEL=deepseek-v4-flash"
Write-Host "KEY_LENGTH=$($apiKey.Length)"
