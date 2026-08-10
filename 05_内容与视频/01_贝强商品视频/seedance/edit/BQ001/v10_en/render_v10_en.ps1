$ErrorActionPreference = 'Stop'

$ffmpeg = 'C:\Users\spq\AppData\Roaming\Python\Python311\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..\..')).Path
$seedance = Join-Path $workspace '05_内容与视频\01_贝强商品视频\seedance'
$edit = $PSScriptRoot
$segments = Join-Path $edit 'segments'
New-Item -ItemType Directory -Force -Path $segments | Out-Null
Set-Location $edit

function BaseFilter {
    return 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=24,format=yuv420p'
}

function Render-VideoSegment {
    param([string]$Source, [double]$Start, [double]$Duration, [string]$Output)
    & $ffmpeg -hide_banner -loglevel error -y -ss $Start -i $Source -t $Duration -an -vf (BaseFilter) -c:v libx264 -preset medium -crf 16 -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart $Output
    if ($LASTEXITCODE -ne 0) { throw "Failed to render $Output" }
}

function Render-OverlaySegment {
    param(
        [string]$Source,
        [double]$Start,
        [double]$Duration,
        [string]$OverlayDirectory,
        [string]$Output
    )
    $pattern = Join-Path $OverlayDirectory 'frame_%04d.png'
    $filter = '[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=24[base];[1:v]format=rgba[graphic];[base][graphic]overlay=0:0:shortest=1,format=yuv420p[out]'
    & $ffmpeg -hide_banner -loglevel error -y -ss $Start -i $Source -framerate 24 -i $pattern -t $Duration -an -filter_complex $filter -map '[out]' -c:v libx264 -preset medium -crf 16 -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart $Output
    if ($LASTEXITCODE -ne 0) { throw "Failed to render $Output" }
}

function Render-ColorSegment {
    param([string]$Source, [double]$Duration, [string]$Output)
    $filter = "crop=800:500:0:150,scale=1120:700,crop=1080:675:x='20+18*sin(n/7)':y=12,pad=1080:1920:0:622:color=white,fps=24,format=yuv420p"
    & $ffmpeg -hide_banner -loglevel error -y -loop 1 -i $Source -t $Duration -an -vf $filter -c:v libx264 -preset medium -crf 16 -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart $Output
    if ($LASTEXITCODE -ne 0) { throw "Failed to render $Output" }
}

$v2 = Join-Path $seedance 'BQ001_WideToeBox_ProductProof_V2_20260728.mp4'
$warm = Join-Path $seedance 'BQ001_CN_Douyin_WarmProductFilm_V8_20260730.mp4'
$toePair = Join-Path $seedance 'BQ001_TikTok_EN_ToeShape_V9_20260801.mp4'
$walk = Join-Path $seedance 'BQ001_TikTok_EN_SideWalk_V9_20260801.mp4'
$overlays = Join-Path $edit 'overlays'

$colorImages = @{}
foreach ($fileName in @('all_black.jpg', 'black_white.jpg', 'white.jpg')) {
    $colorImages[$fileName] = Get-ChildItem -Path $workspace -Recurse -File -Filter $fileName |
        Where-Object { $_.FullName -match 'BQ001' } |
        Sort-Object { $_.FullName.Length } |
        Select-Object -First 1 -ExpandProperty FullName
    if (-not $colorImages[$fileName]) { throw "Missing BQ001 color image: $fileName" }
}

Render-VideoSegment $warm 0.10 2.50 (Join-Path $segments '01_warm_hook.mp4')
Render-VideoSegment $v2 0.10 1.96 (Join-Path $segments '02_exact_shape.mp4')
Render-VideoSegment $toePair 0.00 3.10 (Join-Path $segments '03_pair_shape.mp4')
Render-OverlaySegment $warm 5.40 2.60 (Join-Path $overlays 'toe') (Join-Path $segments '04_top_outline.mp4')
Render-OverlaySegment $warm 2.80 2.60 (Join-Path $overlays 'knit') (Join-Path $segments '05_knit_airflow.mp4')
Render-OverlaySegment $v2 5.18 2.81 (Join-Path $overlays 'collar') (Join-Path $segments '06_slip_on.mp4')
Render-OverlaySegment $v2 8.00 2.00 (Join-Path $overlays 'sole') (Join-Path $segments '07_eva_sole.mp4')
Render-VideoSegment $walk 0.25 2.22 (Join-Path $segments '08_side_walk.mp4')
Render-ColorSegment $colorImages['all_black.jpg'] 0.74 (Join-Path $segments '09_black.mp4')
Render-ColorSegment $colorImages['black_white.jpg'] 0.74 (Join-Path $segments '10_black_white.mp4')
Render-ColorSegment $colorImages['white.jpg'] 0.74 (Join-Path $segments '11_white.mp4')
Render-VideoSegment $warm 0.25 2.23 (Join-Path $segments '12_factory.mp4')
Render-VideoSegment $v2 8.00 2.00 (Join-Path $segments '13_cta_side_a.mp4')
Render-VideoSegment $v2 0.10 2.02 (Join-Path $segments '14_cta_side_b.mp4')
Render-VideoSegment $v2 6.25 1.84 (Join-Path $segments '15_cta_detail.mp4')

$concatPath = Join-Path $edit 'concat_v10_en.txt'
@(
    '01_warm_hook.mp4','02_exact_shape.mp4','03_pair_shape.mp4','04_top_outline.mp4',
    '05_knit_airflow.mp4','06_slip_on.mp4','07_eva_sole.mp4','08_side_walk.mp4',
    '09_black.mp4','10_black_white.mp4','11_white.mp4','12_factory.mp4',
    '13_cta_side_a.mp4','14_cta_side_b.mp4','15_cta_detail.mp4'
) | ForEach-Object { "file 'segments/$_'" } | Set-Content -LiteralPath $concatPath -Encoding ascii

$silentMaster = Join-Path $edit 'silent_master_v10_en.mp4'
& $ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i $concatPath -c copy $silentMaster
if ($LASTEXITCODE -ne 0) { throw 'Failed to concatenate V10 segments' }

$voice = Join-Path $edit 'voice_emma_v10.mp3'
$final = Join-Path $edit 'final_v10_en.mp4'
$audioFilter = "[1:a]aresample=48000,volume=1.18,afade=t=in:st=0:d=0.06,apad=pad_dur=30[voice];[2:a]aresample=48000,volume=0.10,aloop=loop=-1:size=2147483647,atrim=0:30,afade=t=in:st=0:d=0.4,afade=t=out:st=28.8:d=1.2[music];[voice][music]amix=inputs=2:duration=longest:dropout_transition=0,loudnorm=I=-16:LRA=8:TP=-1.5[aout]"
& $ffmpeg -hide_banner -loglevel error -y -i $silentMaster -i $voice -stream_loop -1 -i $v2 -filter_complex $audioFilter -map 0:v -map '[aout]' -t 30 -vf "ass='captions_v10_en.ass'" -c:v libx264 -preset medium -crf 16 -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart $final
if ($LASTEXITCODE -ne 0) { throw 'Failed to render V10 final' }

Write-Output $final
