param(
    [string]$EnvPath = (Join-Path $PSScriptRoot "..\.env")
)

$ErrorActionPreference = "Stop"

function New-Secret {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes)
}

$resolvedPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($EnvPath)
$lines = @()
if (Test-Path -LiteralPath $resolvedPath) {
    $lines = @(Get-Content -LiteralPath $resolvedPath)
} else {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $resolvedPath) | Out-Null
}

$required = @{
    SECRET_KEY = New-Secret
    JWT_SECRET_KEY = New-Secret
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
}

$seen = @{}
$next = foreach ($line in $lines) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=') {
        $key = $Matches[1]
        if ($required.ContainsKey($key)) {
            $seen[$key] = $true
            $value = ($line -replace '^\s*[A-Za-z_][A-Za-z0-9_]*\s*=', '').Trim()
            if ($key -eq "EMAIL_BACKEND" -and (!$value -or $value -match 'console|locmem')) {
                "$key=$($required[$key])"
            } elseif ($key -ne "EMAIL_BACKEND" -and (!$value -or $value -match 'changeme|default|secret|placeholder')) {
                "$key=$($required[$key])"
            } else {
                $line
            }
            continue
        }
    }
    $line
}

foreach ($key in $required.Keys) {
    if (!$seen.ContainsKey($key)) {
        $next += "$key=$($required[$key])"
    }
}

$next | Set-Content -LiteralPath $resolvedPath -Encoding UTF8
Write-Host "Secrets ensured in $resolvedPath"
