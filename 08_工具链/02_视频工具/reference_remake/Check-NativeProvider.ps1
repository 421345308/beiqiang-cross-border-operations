[CmdletBinding()]
param([Parameter(Mandatory)][string]$Workspace)
$ErrorActionPreference = 'Stop'
$nativeRoot = (Resolve-Path -LiteralPath $Workspace).Path
$profilePath = Join-Path $nativeRoot 'hypit.runtime.json'
$nativeProfile = Get-Content -LiteralPath $profilePath -Raw -Encoding utf8 | ConvertFrom-Json
$job = Get-Content -LiteralPath $nativeProfile.endpoints.'libtv.reference'.config.prepared -Raw -Encoding utf8 | ConvertFrom-Json
$assetRoots = @((Split-Path -Parent $job.reference_video.path)) +
    @($job.reference_images | ForEach-Object { Split-Path -Parent $_.path })
$argsBase = @('--workspace', $nativeRoot)
foreach ($assetRoot in @($assetRoots | Select-Object -Unique)) { $argsBase += @('--asset-root', $assetRoot) }
$launcher = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '../Hypit/Invoke-Hypit.ps1'
& $launcher check (Join-Path $nativeRoot 'whole.svml') @argsBase
if ($LASTEXITCODE -ne 0) { throw 'Hypit Source validation failed.' }
& $launcher plan (Join-Path $nativeRoot 'whole.svrun') --runtime $profilePath @argsBase
if ($LASTEXITCODE -ne 0) { throw 'Hypit Provider planning failed.' }
Write-Output 'Source and Provider plan checked. This is not a paid authorization, live generation or creative acceptance.'
