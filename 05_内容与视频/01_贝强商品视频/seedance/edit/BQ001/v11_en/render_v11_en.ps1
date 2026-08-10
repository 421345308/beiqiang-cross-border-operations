$ErrorActionPreference = 'Stop'

$ffmpeg = 'C:\Users\spq\AppData\Roaming\Python\Python311\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..\..')).Path
$seedance = Join-Path $workspace '05_内容与视频\01_贝强商品视频\seedance'
$segments = Join-Path $PSScriptRoot 'segments'
New-Item -ItemType Directory -Force -Path $segments | Out-Null
Set-Location $PSScriptRoot

function Render-SourceSegment {
    param([string]$Source, [double]$Start, [double]$Duration, [string]$Output)
    $videoFilter = 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=24,format=yuv420p'
    & $ffmpeg -hide_banner -loglevel error -y -ss $Start -i $Source -t $Duration -an -vf $videoFilter `
        -c:v libx264 -preset medium -crf 15 -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart $Output
    if ($LASTEXITCODE -ne 0) { throw "Failed to render $Output" }
}

$warm = Join-Path $seedance 'BQ001_CN_Douyin_WarmProductFilm_V8_20260730.mp4'
$walk = Join-Path $seedance 'BQ001_TikTok_EN_SideWalk_V9_20260801.mp4'
$proof = Join-Path $seedance 'BQ001_WideToeBox_ProductProof_V2_20260728.mp4'

Render-SourceSegment $warm 0.00 3.00 (Join-Path $segments '01_hook.mp4')
Render-SourceSegment $walk 0.15 3.50 (Join-Path $segments '06_walk.mp4')
Render-SourceSegment $proof 8.00 2.00 (Join-Path $segments '08_cta.mp4')

$concatFile = Join-Path $PSScriptRoot 'concat_v11_en.txt'
@(
    "file 'segments/01_hook.mp4'",
    "file '02_shape_card.mp4'",
    "file '03_knit_card.mp4'",
    "file '04_slipon_card.mp4'",
    "file '05_sole_card.mp4'",
    "file 'segments/06_walk.mp4'",
    "file '07_colors_card.mp4'",
    "file 'segments/08_cta.mp4'"
) | Set-Content -LiteralPath $concatFile -Encoding ascii

$silentMaster = Join-Path $PSScriptRoot 'silent_master_v11_en.mp4'
& $ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i $concatFile -c copy $silentMaster
if ($LASTEXITCODE -ne 0) { throw 'Failed to concatenate V11 segments' }

$voice = Join-Path $PSScriptRoot 'voice_ava_v11.mp3'
$final = Join-Path $PSScriptRoot 'final_v11_en.mp4'
$audioFilter = "[1:a]aresample=48000,volume=1.08,adelay=120|120,afade=t=in:st=0:d=0.06,afade=t=out:st=27.9:d=0.35,apad=pad_dur=30[voice];[2:a]aresample=48000,volume=0.075,aloop=loop=-1:size=2147483647,atrim=0:30,afade=t=in:st=0:d=0.5,afade=t=out:st=28.7:d=1.3[music];[voice][music]amix=inputs=2:duration=longest:dropout_transition=0,loudnorm=I=-16:LRA=7:TP=-1.5[aout]"
& $ffmpeg -hide_banner -loglevel error -y -i $silentMaster -i $voice -stream_loop -1 -i $proof `
    -filter_complex $audioFilter -map 0:v -map '[aout]' -frames:v 720 -vf "ass='overlays_v11.ass'" `
    -c:v libx264 -preset medium -crf 15 -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart $final
if ($LASTEXITCODE -ne 0) { throw 'Failed to render V11 final' }

Write-Output $final
