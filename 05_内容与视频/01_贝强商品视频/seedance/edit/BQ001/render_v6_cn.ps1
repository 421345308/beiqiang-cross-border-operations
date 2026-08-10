$ErrorActionPreference = "Stop"

$ffmpeg = "C:\Users\spq\AppData\Roaming\Python\Python311\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
$workspace = (Get-Location).Path
$editDir = Join-Path $workspace "05_内容与视频\01_贝强商品视频\seedance\edit\BQ001"
$segmentDir = Join-Path $editDir "segments_v6_cn"
$sourceDir = Join-Path $workspace "05_内容与视频\01_贝强商品视频\seedance"

New-Item -ItemType Directory -Force -Path $segmentDir | Out-Null

$segments = @(
    @{ Name = "01_host_hook"; Source = "BQ001_CN_Douyin_FemalePresenter_V6_20260729.mp4"; Start = 0.0; Duration = 2.4 },
    @{ Name = "02_side_proof"; Source = "BQ001_WideToeBox_ProductProof_V2_20260728.mp4"; Start = 0.2; Duration = 1.5 },
    @{ Name = "03_top_proof"; Source = "BQ001_WideToeBox_ProductProof_V2_20260728.mp4"; Start = 2.2; Duration = 1.7 },
    @{ Name = "04_host_explain"; Source = "BQ001_CN_Douyin_FemalePresenter_V6_20260729.mp4"; Start = 5.6; Duration = 3.3 },
    @{ Name = "05_daily_walk"; Source = "BQ001_LifestyleWalk_Insert_V3_20260729.mp4"; Start = 3.5; Duration = 1.85 },
    @{ Name = "06_host_close"; Source = "BQ001_CN_Douyin_FemalePresenter_V6_20260729.mp4"; Start = 10.75; Duration = 1.3 },
    @{ Name = "07_exact_hero"; Source = "BQ001_WideToeBox_ProductProof_V2_20260728.mp4"; Start = 7.45; Duration = 2.55 }
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
        -f concat -safe 0 -i "concat_v6_cn.txt" `
        -c copy "visual_master_v6_cn.mp4"

    & $ffmpeg -y -hide_banner -loglevel error `
        -i "visual_master_v6_cn.mp4" `
        -i (Join-Path $sourceDir "BQ001_CN_Douyin_FemalePresenter_V6_20260729.mp4") `
        -stream_loop 1 -i (Join-Path $sourceDir "BQ001_WideToeBox_ProductProof_V2_20260728.mp4") `
        -filter_complex "[0:v]eq=contrast=1.02:saturation=0.97:brightness=0.004,subtitles='captions_v6_cn.ass'[v];[1:a]atrim=0:12.1,asetpts=PTS-STARTPTS,volume=1.05,highpass=f=75,lowpass=f=13000,afade=t=in:st=0:d=0.03,afade=t=out:st=11.9:d=0.15[voice];[2:a]atrim=0:14.6,asetpts=PTS-STARTPTS,volume=0.075,afade=t=in:st=0:d=0.5,afade=t=out:st=13.7:d=0.9[music];[voice][music]amix=inputs=2:duration=longest:normalize=0,loudnorm=I=-14:TP=-1:LRA=7[a]" `
        -map "[v]" -map "[a]" -t 14.6 `
        -c:v libx264 -preset slow -crf 17 -profile:v high -level 4.1 -pix_fmt yuv420p `
        -c:a aac -b:a 192k -ar 48000 -movflags +faststart `
        "final_v6_cn.mp4"
}
finally {
    Pop-Location
}
