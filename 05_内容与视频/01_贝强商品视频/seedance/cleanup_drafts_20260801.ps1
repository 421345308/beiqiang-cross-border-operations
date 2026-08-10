$ErrorActionPreference = 'Stop'

$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$seedance = (Resolve-Path $PSScriptRoot).Path
$edit = (Resolve-Path (Join-Path $seedance 'edit\BQ001')).Path

if (-not $seedance.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Seedance path is outside the workspace.'
}
if (-not $edit.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'BQ001 edit path is outside the workspace.'
}

$library = Join-Path $edit 'source_library'
New-Item -ItemType Directory -Force -Path $library | Out-Null

$moveMap = @{
    'BQ001_WideToeBox_ProductProof_V2_20260728.mp4' = 'BQ001_Source_ExactProductProof_V2.mp4'
    'BQ001_CN_Douyin_WarmProductFilm_V8_20260730.mp4' = 'BQ001_Source_WarmProductFilm_V8.mp4'
    'BQ001_CN_Douyin_GreenWalk_V8_20260730.mp4' = 'BQ001_Source_GreenWalk_V8.mp4'
    'BQ001_CN_Douyin_GentlePresenter_V7B_20260729.mp4' = 'BQ001_Source_GentlePresenter_V7B.mp4'
    'BQ001_TikTok_EN_SideWalk_V9_20260801.mp4' = 'BQ001_Source_SideWalk_V9.mp4'
}

foreach ($entry in $moveMap.GetEnumerator()) {
    $source = Join-Path $seedance $entry.Key
    $destination = Join-Path $library $entry.Value
    if (Test-Path -LiteralPath $source) {
        Move-Item -LiteralPath $source -Destination $destination -Force
    }
}

$keepRoot = @(
    'BQ001_Douyin_CN_ProductVisual_Enhanced_V8_20260730.mp4',
    'BQ001_TikTok_EN_EditorialSmooth_V12_20260801.mp4',
    'BQ017_A008_TikTok_Lifestyle_V2_20260728.mp4'
)

$deleted = New-Object System.Collections.Generic.List[System.IO.FileInfo]
$rootVideos = Get-ChildItem -LiteralPath $seedance -File -Filter '*.mp4'
foreach ($video in $rootVideos) {
    if ($video.Name -notin $keepRoot) {
        $deleted.Add($video)
        Remove-Item -LiteralPath $video.FullName -Force
    }
}

$editVideos = Get-ChildItem -LiteralPath $edit -Recurse -File -Filter '*.mp4'
foreach ($video in $editVideos) {
    if (-not $video.FullName.StartsWith($library, [System.StringComparison]::OrdinalIgnoreCase)) {
        $deleted.Add($video)
        Remove-Item -LiteralPath $video.FullName -Force
    }
}

$freedBytes = ($deleted | Measure-Object Length -Sum).Sum
Write-Output "DELETED_FILES=$($deleted.Count)"
Write-Output "FREED_BYTES=$freedBytes"
Write-Output '---RETAINED ROOT---'
Get-ChildItem -LiteralPath $seedance -File -Filter '*.mp4' | Select-Object Name, Length
Write-Output '---SOURCE LIBRARY---'
Get-ChildItem -LiteralPath $library -File -Filter '*.mp4' | Select-Object Name, Length
