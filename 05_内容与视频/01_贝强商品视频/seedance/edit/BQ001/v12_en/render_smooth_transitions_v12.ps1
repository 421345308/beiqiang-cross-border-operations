$ErrorActionPreference = 'Stop'

$ffmpeg = 'C:\Users\spq\AppData\Roaming\Python\Python311\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe'
$source = (Resolve-Path (Join-Path $PSScriptRoot '..\v11_en\final_v11_en.mp4')).Path
$edit = $PSScriptRoot
$segments = Join-Path $edit 'segments'
New-Item -ItemType Directory -Force -Path $segments | Out-Null
Set-Location $edit

$boundaries = @(3.0, 8.5, 13.5, 18.0, 22.0, 25.5, 28.0)
$halfTransition = 0.25

function Encode-NormalSegment {
    param([double]$Start, [double]$Duration, [string]$Output)
    & $ffmpeg -hide_banner -loglevel error -y -ss $Start -i $source -t $Duration -an `
        -vf 'fps=24,format=yuv420p' -c:v libx264 -preset medium -crf 15 `
        -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart $Output
    if ($LASTEXITCODE -ne 0) { throw "Failed to render $Output" }
}

function Encode-TransitionSegment {
    param([double]$Boundary, [string]$Output)
    $leftStart = $Boundary - $halfTransition
    $rightStart = $Boundary + $halfTransition
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($Output)
    $leftFrame = Join-Path $segments ($baseName + '_left.png')
    $rightFrame = Join-Path $segments ($baseName + '_right.png')
    & $ffmpeg -hide_banner -loglevel error -y -ss $leftStart -i $source -frames:v 1 $leftFrame
    if ($LASTEXITCODE -ne 0) { throw "Failed to extract $leftFrame" }
    & $ffmpeg -hide_banner -loglevel error -y -ss $rightStart -i $source -frames:v 1 $rightFrame
    if ($LASTEXITCODE -ne 0) { throw "Failed to extract $rightFrame" }
    $filter = "[0:v][1:v]xfade=transition=smoothleft:duration=0.5:offset=0,format=yuv420p[out]"
    & $ffmpeg -hide_banner -loglevel error -y -loop 1 -framerate 24 -i $leftFrame -loop 1 -framerate 24 -i $rightFrame `
        -filter_complex $filter -map '[out]' -an -t 0.5 -c:v libx264 -preset medium -crf 15 `
        -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart $Output
    if ($LASTEXITCODE -ne 0) { throw "Failed to render $Output" }
}

$entries = New-Object System.Collections.Generic.List[string]
$cursor = 0.0
for ($index = 0; $index -lt $boundaries.Count; $index++) {
    $boundary = $boundaries[$index]
    $normalEnd = $boundary - $halfTransition
    $normalDuration = $normalEnd - $cursor
    $normalName = ('{0:D2}_normal.mp4' -f ($index * 2 + 1))
    Encode-NormalSegment $cursor $normalDuration (Join-Path $segments $normalName)
    $entries.Add("file 'segments/$normalName'")

    $transitionName = ('{0:D2}_transition.mp4' -f ($index * 2 + 2))
    Encode-TransitionSegment $boundary (Join-Path $segments $transitionName)
    $entries.Add("file 'segments/$transitionName'")
    $cursor = $boundary + $halfTransition
}

$finalNormalName = '15_normal.mp4'
Encode-NormalSegment $cursor (30.0 - $cursor) (Join-Path $segments $finalNormalName)
$entries.Add("file 'segments/$finalNormalName'")

$concatFile = Join-Path $edit 'concat_v12_en.txt'
$entries | Set-Content -LiteralPath $concatFile -Encoding ascii
$silent = Join-Path $edit 'silent_master_v12_en.mp4'
& $ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i $concatFile -c copy $silent
if ($LASTEXITCODE -ne 0) { throw 'Failed to concatenate V12 segments' }

$final = Join-Path $edit 'final_v12_en.mp4'
& $ffmpeg -hide_banner -loglevel error -y -i $silent -i $source -map 0:v:0 -map 1:a:0 `
    -frames:v 720 -c:v copy -c:a copy -movflags +faststart $final
if ($LASTEXITCODE -ne 0) { throw 'Failed to mux V12 final' }

Write-Output $final
