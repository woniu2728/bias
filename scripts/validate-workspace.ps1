param(
    [switch]$BuildFrontend
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SiteRoot = Resolve-Path (Join-Path $ScriptDir "..")
$WorkspaceRoot = Resolve-Path (Join-Path $SiteRoot "..")
$CoreRoot = Join-Path $WorkspaceRoot "bias_core"
$UsersRoot = Join-Path $WorkspaceRoot "bias-ext-users"

function Step($Message) {
    Write-Host ""
    Write-Host "==> $Message"
}

function Run($Command, $WorkingDirectory) {
    Write-Host "[$WorkingDirectory] $Command"
    Push-Location $WorkingDirectory
    try {
        powershell -NoProfile -ExecutionPolicy Bypass -Command $Command
    }
    finally {
        Pop-Location
    }
}

Step "Compile Python packages"
$compileTargets = @($CoreRoot) + @(
    Get-ChildItem -Path $WorkspaceRoot -Directory -Filter "bias-ext-*" | ForEach-Object { $_.FullName }
)
foreach ($target in $compileTargets) {
    Run "python -m compileall -q ." $target
}

Step "Import extension backend entries"
Push-Location $UsersRoot
try {
    $env:DJANGO_SETTINGS_MODULE = "tests.settings"
    @'
import django
import importlib
import json
from pathlib import Path

django.setup()
failed = []
for manifest in Path("..").glob("bias-ext-*/extension.json"):
    data = json.loads(manifest.read_text(encoding="utf-8"))
    entry = (data.get("backend", {}).get("entry") or "").split(":", 1)[0]
    if not entry:
        continue
    try:
        importlib.import_module(entry)
    except Exception as exc:
        failed.append((data.get("id"), entry, exc))
        print(f"FAIL {data.get('id')} {entry}: {exc!r}")
if failed:
    raise SystemExit(1)
print("All backend entries import successfully.")
'@ | python -
}
finally {
    Pop-Location
}

Step "Scan split package import boundaries"
Push-Location $WorkspaceRoot
try {
    $matches = rg -n "from apps\.|import apps\.|from extensions\.|import extensions\." `
        -g "*.py" `
        -g "!bias/**" `
        -g "!pyflarum/**" `
        -g "!**/tests.py" `
        -g "!**/tests/**" `
        -g "!**/__pycache__/**" `
        -g "!**/*.egg-info/**" `
        -g "!**/build/**" `
        -g "!**/dist/**" `
        . 2>$null
    if ($LASTEXITCODE -eq 0) {
        $matches
        throw "Old monolith import boundary references remain."
    }
    if ($LASTEXITCODE -gt 1) {
        throw "Boundary scan failed."
    }
    Write-Host "No old monolith import references found in split packages."
}
finally {
    Pop-Location
}

if ($BuildFrontend) {
    Step "Check synced extension frontend sources"
    Run "npm run check:extension-sources" (Join-Path $SiteRoot "frontend")

    Step "Build site frontend"
    Run "npm install; npm run build" (Join-Path $SiteRoot "frontend")
}

Step "Workspace validation complete"
