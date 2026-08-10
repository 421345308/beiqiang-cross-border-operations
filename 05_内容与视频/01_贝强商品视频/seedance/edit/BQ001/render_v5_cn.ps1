$ErrorActionPreference = "Stop"

$ffmpeg = "C:\Users\spq\AppData\Roaming\Python\Python311\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
$workspace = (Get-Location).Path
$editDir = Join-Path $workspace "05_内容与视频\01_贝强商品视频\seedance\edit\BQ001"
$segmentDir = Join-Path $editDir "segments_v5_cn"
$sourceDir = Join-Path $workspace "05_内容与视频\01_贝强商品视频\seedance"

New-Item -ItemType Directory -Force -Path $segmentDir | Out-Null

$segments = @(
    @{ Name = "01_pain"; Source = "BQ001_CN_Douyin_PainHook_V5_20260729.mp4"; Start = 0.0; Duration = 3.88 },
    @{ Name = "02_side"; Source = "BQ001_WideToeBox_ProductProof_V2_20260728.mp4"; Start = 0.0; Duration = 2.92 },
    @{ Name = "03_top"; Source = "BQ001_WideToeBox_ProductProof_V2_20260728.mp4"; Start = 2.2; Duration = 2.0 },
    @{ Name = "04_macro"; Source = "BQ001_WideToeBox_ProductProof_V2_20260728.mp4"; Start = 4.5; Duration = 1.4 },
    @{ Name = "05_home"; Source = "BQ001_LifestyleWalk_Insert_V3_20260729.mp4"; Start = 3.3; Duration = 2.2 },
    @{ Name = "06_travel"; Source = "BQ001_TravelLifestyle_Insert_V4_20260729.mp4"; Start = 4.4; Duration = 1.6 },
    @{ Name = "07_hero"; Source = "BQ001_WideToeBox_ProductProof_V2_20260728.mp4"; Start = 8.5; Duration = 1.5 }
)

foreach ($segment in $segments) {
    $inputPath = Join-Path $sourceDir $segment.Source
    $outputPath = Join-Path $segmentDir "$($segment.Name).mp4"
    & $ffmpeg -y -hide_banner -loglevel error `
        -i $inputPath -ss $segment.Start -t $segment.Duration `
        -an -vf "scale=1080:1920:flags=lanczos,fps=24,format=yuv420p" `
        -c:v libx264 -preset medium -crf 16 -profile:v high -level 4.1 `
        -movflags +faststart $outputPath
}

Push-Location $editDir
try {
    & $ffmpeg -y -hide_banner -loglevel error `
        -f concat -safe 0 -i "concat_v5_cn.txt" `
        -c copy "visual_master_v5_cn.mp4"

    & $ffmpeg -y -hide_banner -loglevel error `
        -i "visual_master_v5_cn.mp4" `
        -i "voiceover_v5_cn.mp3" `
        -stream_loop 1 -i (Join-Path $sourceDir "BQ001_WideToeBox_ProductProof_V2_20260728.mp4") `
        -filter_complex "[0:v]eq=contrast=1.025:saturation=0.96:brightness=0.006,subtitles='captions_v5_cn.ass'[v];[1:a]adelay=100|100,volume=1.2,highpass=f=80,lowpass=f=12500,afade=t=in:st=0:d=0.03,afade=t=out:st=12.35:d=0.15[voice];[2:a]atrim=0:15.5,asetpts=PTS-STARTPTS,volume=0.11,afade=t=in:st=0:d=0.4,afade=t=out:st=14.7:d=0.8[music];anoisesrc=color=pink:duration=0.18:amplitude=0.08,highpass=f=700,lowpass=f=5000,afade=t=in:st=0:d=0.04,afade=t=out:st=0.05:d=0.13,adelay=3880[whoosh];[voice][music][whoosh]amix=inputs=3:duration=longest:normalize=0,loudnorm=I=-14:TP=-1:LRA=7[a]" `
        -map "[v]" -map "[a]" -t 15.5 `
        -c:v libx264 -preset slow -crf 17 -profile:v high -level 4.1 -pix_fmt yuv420p `
        -c:a aac -b:a 192k -ar 48000 -movflags +faststart `
        "final_v5_cn.mp4"
}
finally {
    Pop-Location
}
