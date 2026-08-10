$ErrorActionPreference = 'Stop'

$ffmpeg = 'C:\Users\spq\AppData\Roaming\Python\Python311\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..\..')).Path
$seedance = Join-Path $workspace '05_内容与视频\01_贝强商品视频\seedance'
$edit = Join-Path $seedance 'edit\BQ001\v9_en'
$segments = Join-Path $edit 'segments'
New-Item -ItemType Directory -Force -Path $segments | Out-Null
Set-Location $edit

function Render-VideoSegment {
    param(
        [string]$Source,
        [double]$Start,
        [double]$Duration,
        [string]$Output,
        [string]$ExtraFilter = ''
    )
    $baseFilter = 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=24,format=yuv420p'
    if ($ExtraFilter) {
        $baseFilter = "$baseFilter,$ExtraFilter"
    }
    & $ffmpeg -hide_banner -loglevel error -y -ss $Start -i $Source -t $Duration -an -vf $baseFilter -c:v libx264 -preset medium -crf 16 -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart $Output
    if ($LASTEXITCODE -ne 0) { throw "Failed to render $Output" }
}

function Render-StillSegment {
    param(
        [string]$Source,
        [double]$Duration,
        [string]$Output,
        [string]$Zoom = '1.04'
    )
    $filter = "split=2[bg][fg];[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=35,eq=brightness=-0.08[bg2];[fg]scale=920:920:force_original_aspect_ratio=decrease[shoe];[bg2][shoe]overlay=(W-w)/2:(H-h)/2,fps=24,format=yuv420p"
    & $ffmpeg -hide_banner -loglevel error -y -loop 1 -i $Source -t $Duration -an -filter_complex $filter -c:v libx264 -preset medium -crf 16 -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart $Output
    if ($LASTEXITCODE -ne 0) { throw "Failed to render $Output" }
}

function Render-VideoFreezeSegment {
    param(
        [string]$Source,
        [double]$Start,
        [double]$MotionDuration,
        [double]$TotalDuration,
        [string]$Output
    )
    $holdDuration = $TotalDuration - $MotionDuration
    $filter = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=24,tpad=stop_mode=clone:stop_duration=$holdDuration,format=yuv420p"
    & $ffmpeg -hide_banner -loglevel error -y -ss $Start -i $Source -t $MotionDuration -an -vf $filter -c:v libx264 -preset medium -crf 16 -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart $Output
    if ($LASTEXITCODE -ne 0) { throw "Failed to render $Output" }
}

$v2 = Join-Path $seedance 'BQ001_WideToeBox_ProductProof_V2_20260728.mp4'
$creator = Join-Path $seedance 'BQ001_TikTok_EN_CreatorHook_V9_20260801.mp4'
$toe = Join-Path $seedance 'BQ001_TikTok_EN_ToeShape_V9_20260801.mp4'
$knit = Join-Path $seedance 'BQ001_TikTok_EN_KnitPress_V9_20260801.mp4'
$stand = Join-Path $seedance 'BQ001_TikTok_EN_StandUp_V9_20260801.mp4'
$walk = Join-Path $seedance 'BQ001_TikTok_EN_SideWalk_V9_20260801.mp4'
$warm = Join-Path $seedance 'BQ001_CN_Douyin_WarmProductFilm_V8_20260730.mp4'
$colorImages = @{}
foreach ($fileName in @('all_black.jpg', 'black_white.jpg', 'white.jpg')) {
    $colorImages[$fileName] = Get-ChildItem -Path $workspace -Recurse -File -Filter $fileName |
        Where-Object { $_.FullName -match 'BQ001' } |
        Sort-Object { $_.FullName.Length } |
        Select-Object -First 1 -ExpandProperty FullName
    if (-not $colorImages[$fileName]) { throw "Missing BQ001 color image: $fileName" }
}

Render-VideoSegment $v2 3.00 1.20 (Join-Path $segments '01_hook_product.mp4')
Render-VideoSegment $creator 1.35 2.32 (Join-Path $segments '02_creator.mp4')
Render-VideoSegment $toe 0.00 2.00 (Join-Path $segments '03_toe_pair.mp4')
Render-VideoSegment $v2 3.80 2.72 (Join-Path $segments '04_toe_trace.mp4')
Render-VideoSegment $knit 0.15 3.46 (Join-Path $segments '05_knit_press.mp4')
Render-VideoSegment $stand 0.40 2.76 (Join-Path $segments '06_stand_up.mp4')
Render-VideoSegment $v2 8.00 1.84 (Join-Path $segments '07_eva_sole.mp4')
Render-VideoSegment $walk 0.20 2.84 (Join-Path $segments '08_side_walk.mp4')
Render-StillSegment $colorImages['all_black.jpg'] 0.91 (Join-Path $segments '09_color_black.mp4') '1.025'
Render-StillSegment $colorImages['black_white.jpg'] 0.91 (Join-Path $segments '10_color_black_white.mp4') '1.025'
Render-StillSegment $colorImages['white.jpg'] 0.92 (Join-Path $segments '11_color_white.mp4') '1.025'
Render-VideoSegment $warm 0.25 2.16 (Join-Path $segments '12_factory_hero.mp4')
Render-VideoSegment $v2 8.05 1.95 (Join-Path $segments '13_final_hero_a.mp4')
Render-VideoSegment $v2 0.05 2.65 (Join-Path $segments '14_final_hero_b.mp4')
Render-VideoSegment $v2 6.95 1.46 (Join-Path $segments '15_final_detail.mp4')

$concatPath = Join-Path $edit 'concat_v9_en.txt'
@(
    '01_hook_product.mp4',
    '02_creator.mp4',
    '03_toe_pair.mp4',
    '04_toe_trace.mp4',
    '05_knit_press.mp4',
    '06_stand_up.mp4',
    '07_eva_sole.mp4',
    '08_side_walk.mp4',
    '09_color_black.mp4',
    '10_color_black_white.mp4',
    '11_color_white.mp4',
    '12_factory_hero.mp4',
    '13_final_hero_a.mp4',
    '14_final_hero_b.mp4',
    '15_final_detail.mp4'
) | ForEach-Object { "file 'segments/$_'" } | Set-Content -LiteralPath $concatPath -Encoding ascii

$silentMaster = Join-Path $edit 'silent_master_v9_en.mp4'
& $ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i $concatPath -c copy $silentMaster
if ($LASTEXITCODE -ne 0) { throw 'Failed to concatenate V9 segments' }

$voice = Join-Path $edit 'voice_emma_v9.mp3'
$musicSource = $v2
$final = Join-Path $edit 'final_v9_en.mp4'
$audioFilter = "[1:a]aresample=48000,volume=1.18,afade=t=in:st=0:d=0.06,apad=pad_dur=30[voice];[2:a]aresample=48000,volume=0.105,aloop=loop=-1:size=2147483647,atrim=0:30,afade=t=in:st=0:d=0.4,afade=t=out:st=28.8:d=1.2[music];[voice][music]amix=inputs=2:duration=longest:dropout_transition=0,loudnorm=I=-16:LRA=8:TP=-1.5[aout]"
& $ffmpeg -hide_banner -loglevel error -y -i $silentMaster -i $voice -stream_loop -1 -i $musicSource -filter_complex $audioFilter -map 0:v -map '[aout]' -t 30 -c:v libx264 -preset medium -crf 16 -vf "ass='captions_v9_en.ass'" -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart $final
if ($LASTEXITCODE -ne 0) { throw 'Failed to render final V9 video' }

Write-Output $final
