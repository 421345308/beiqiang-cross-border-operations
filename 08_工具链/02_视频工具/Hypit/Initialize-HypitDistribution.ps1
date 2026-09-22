[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$distributionRoot = Join-Path $toolRoot 'distribution'
$hypitRoot = Join-Path $distributionRoot 'node_modules\@hypit\hypit'
$embeddedPackagesRoot = Join-Path $hypitRoot 'packages'
$linkScope = Join-Path $distributionRoot 'node_modules\@hypit'

if (-not (Test-Path -LiteralPath $embeddedPackagesRoot)) {
    throw "Hypit embedded packages were not found: $embeddedPackagesRoot"
}

New-Item -ItemType Directory -Force -Path $linkScope | Out-Null

foreach ($packageDir in Get-ChildItem -LiteralPath $embeddedPackagesRoot -Directory) {
    $manifestPath = Join-Path $packageDir.FullName 'package.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        continue
    }

    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.name -notmatch '^@hypit/([^/]+)$') {
        continue
    }

    $packageName = $Matches[1]
    if ($packageName -eq 'hypit') {
        continue
    }

    $linkPath = Join-Path $linkScope $packageName
    if (-not (Test-Path -LiteralPath $linkPath)) {
        New-Item -ItemType Junction -Path $linkPath -Target $packageDir.FullName | Out-Null
    }
}

$hyperframesScope = Join-Path $distributionRoot 'node_modules\@hyperframes'
New-Item -ItemType Directory -Force -Path $hyperframesScope | Out-Null

foreach ($packageName in @('engine', 'producer')) {
    $machinePackage = Join-Path $env:LOCALAPPDATA "Hypit\packages\@hyperframes\$packageName\0.7.101\node_modules\@hyperframes\$packageName"
    $linkPath = Join-Path $hyperframesScope $packageName
    if ((Test-Path -LiteralPath $machinePackage) -and -not (Test-Path -LiteralPath $linkPath)) {
        New-Item -ItemType Junction -Path $linkPath -Target $machinePackage | Out-Null
    }
}
