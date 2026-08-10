$ErrorActionPreference = 'Stop'

$ffmpeg = 'C:\Users\spq\AppData\Roaming\Python\Python311\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe'
$edit = $PSScriptRoot
$generated = (Resolve-Path (Join-Path $edit '..\generated')).Path
$segments = Join-Path $edit 'segments'
New-Item -ItemType Directory -Force -Path $segments | Out-Null
Set-Location $edit

function Encode-Segment {
    param([string]$Source, [double]$Start, [int]$Frames, [string]$Output)
    & $ffmpeg -hide_banner -loglevel error -y -ss $Start -i $Source -an -frames:v $Frames `
        -vf 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=24,format=yuv420p' `
        -c:v libx264 -preset medium -crf 15 -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart $Output
    if ($LASTEXITCODE -ne 0) { throw "Failed to render $Output" }
}

Encode-Segment (Join-Path $edit '01_hook.mp4') 0.00 59 (Join-Path $segments '01_hook.mp4')
Encode-Segment (Join-Path $generated 'cgt-20260801164719-h5ktq.mp4') 0.10 115 (Join-Path $segments '02_white.mp4')
Encode-Segment (Join-Path $generated 'cgt-20260801163532-5ngj8.mp4') 0.55 67 (Join-Path $segments '03_black.mp4')
Encode-Segment (Join-Path $generated 'cgt-20260801164059-d2c9p.mp4') 0.55 67 (Join-Path $segments '04_khaki.mp4')
Encode-Segment (Join-Path $edit '05_toe.mp4') 0.00 73 (Join-Path $segments '05_toe.mp4')
Encode-Segment (Join-Path $edit '06_upper.mp4') 0.00 68 (Join-Path $segments '06_upper.mp4')
Encode-Segment (Join-Path $edit '07_sole.mp4') 0.00 68 (Join-Path $segments '07_sole.mp4')
Encode-Segment (Join-Path $edit '08_poll.mp4') 0.00 67 (Join-Path $segments '08_poll.mp4')
Encode-Segment (Join-Path $generated 'cgt-20260801164719-h5ktq.mp4') 0.38 104 (Join-Path $segments '09_cta.mp4')

$concatFile = Join-Path $edit 'concat_bq002_v1.txt'
@(
    '01_hook.mp4', '02_white.mp4', '03_black.mp4', '04_khaki.mp4', '05_toe.mp4',
    '06_upper.mp4', '07_sole.mp4', '08_poll.mp4', '09_cta.mp4'
) | ForEach-Object { "file 'segments/$_'" } | Set-Content -LiteralPath $concatFile -Encoding ascii

$silent = Join-Path $edit 'silent_master_bq002_v1.mp4'
& $ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i $concatFile -c copy $silent
if ($LASTEXITCODE -ne 0) { throw 'Failed to concatenate BQ002 V1' }

$voice = Join-Path $edit 'voice_ava_bq002.mp3'
$music = Join-Path $edit 'music_original_118bpm.wav'
$final = Join-Path $edit 'final_bq002_v1.mp4'
$audioFilter = "[1:a]aresample=48000,volume=1.12,adelay=80|80,afade=t=in:st=0:d=0.05,afade=t=out:st=27.75:d=0.25,apad=pad_dur=28.5[voice];[2:a]aresample=48000,volume=0.14,atrim=0:28.5[music];[voice][music]amix=inputs=2:duration=longest:dropout_transition=0,loudnorm=I=-16:LRA=7:TP=-1.5[aout]"
& $ffmpeg -hide_banner -loglevel error -y -i $silent -i $voice -i $music -filter_complex $audioFilter `
    -map 0:v:0 -map '[aout]' -frames:v 684 -vf "ass='captions_bq002.ass'" `
    -c:v libx264 -preset medium -crf 15 -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart $final
if ($LASTEXITCODE -ne 0) { throw 'Failed to render BQ002 V1 final' }

Write-Output $final
