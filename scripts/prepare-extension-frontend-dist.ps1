param(
    [string]$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

$ErrorActionPreference = "Stop"

$extensions = Get-ChildItem -LiteralPath $WorkspaceRoot -Directory -Filter "bias-ext-*"
foreach ($extension in $extensions) {
    $frontend = Join-Path $extension.FullName "frontend"
    if (!(Test-Path -LiteralPath $frontend)) {
        continue
    }

    $dist = Join-Path $frontend "dist"
    if (Test-Path -LiteralPath $dist) {
        Remove-Item -LiteralPath $dist -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $dist | Out-Null

    foreach ($child in Get-ChildItem -LiteralPath $frontend -Force) {
        if ($child.Name -eq "dist") {
            continue
        }
        $target = Join-Path $dist $child.Name
        if ($child.PSIsContainer) {
            Copy-Item -LiteralPath $child.FullName -Destination $target -Recurse -Force
        } else {
            Copy-Item -LiteralPath $child.FullName -Destination $target -Force
        }
    }

    Write-Host "Prepared $($extension.Name) frontend/dist"
}
