$ErrorActionPreference = "Stop"

$ffmpeg = "C:\Users\spq\AppData\Roaming\Python\Python311\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
$workspace = (Get-Location).Path
$editDir = Join-Path $workspace "05_内容与视频\01_贝强商品视频\seedance\edit\BQ001"
$segmentDir = Join-Path $editDir "segments_v7_cn"
$sourceDir = Join-Path $workspace "05_内容与视频\01_贝强商品视频\seedance"

New-Item -ItemType Directory -Force -Path $segmentDir | Out-Null

$segments = @(
    @{ Name = "01_host_hook"; Source = "BQ001_CN_Douyin_GentlePresenter_V7B_20260729.mp4"; Start = 0.0; Duration = 2.25 },
    @{ Name = "02_side_proof"; Source = "BQ001_WideToeBox_ProductProof_V2_20260728.mp4"; Start = 0.0; Duration = 1.45 },
    @{ Name = "03_top_proof"; Source = "BQ001_WideToeBox_ProductProof_V2_20260728.mp4"; Start = 2.2; Duration = 1.45 },
    @{ Name = "04_host_material"; Source = "BQ001_CN_Douyin_GentlePresenter_V7B_20260729.mp4"; Start = 5.15; Duration = 1.55 },
    @{ Name = "05_knit_macro"; Source = "BQ001_WideToeBox_ProductProof_V2_20260728.mp4"; Start = 4.5; Duration = 1.82 },
    @{ Name = "06_home_walk"; Source = "BQ001_LifestyleWalk_Insert_V3_20260729.mp4"; Start = 3.4; Duration = 1.58 },
    @{ Name = "07_travel_walk"; Source = "BQ001_TravelLifestyle_Insert_V4_20260729.mp4"; Start = 0.3; Duration = 1.3 },
    @{ Name = "08_host_close"; Source = "BQ001_CN_Douyin_GentlePresenter_V7B_20260729.mp4"; Start = 11.4; Duration = 0.7 },
    @{ Name = "09_travel_seated"; Source = "BQ001_TravelLifestyle_Insert_V4_20260729.mp4"; Start = 4.5; Duration = 1.4 },
    @{ Name = "10_exact_hero"; Source = "BQ001_WideToeBox_ProductProof_V2_20260728.mp4"; Start = 8.0; Duration = 2.0 }
)

foreach ($segment in $segments) {
    $inputPath = Join-Path $sourceDir $segment.Source
    $outputPath = Join-Path $segmentDir "$($segment.Name).mp4"
    & $ffmpeg -y -hide_banner -loglevel error `
        -i $inputPath -ss $segment.Start -t $segment.Duration `
        -an -vf "scale=1080:1920:flags=lanczos,fps=24,format=yuv420p" `
        -c:v libx264 -preset medium -crf 16 -profile:v high -level 4.1 `
        -movflags +faststart $outputPath
    if ($LASTEXITCODE -ne 0) { throw "Segment render failed: $($segment.Name)" }
}

Push-Location $editDir
try {
    & $ffmpeg -y -hide_banner -loglevel error `
        -f concat -safe 0 -i "concat_v7_cn.txt" `
        -c copy "visual_master_v7_cn.mp4"
    if ($LASTEXITCODE -ne 0) { throw "Visual concat failed." }

    & $ffmpeg -y -hide_banner -loglevel error `
        -i "visual_master_v7_cn.mp4" `
        -i (Join-Path $sourceDir "BQ001_CN_Douyin_GentlePresenter_V7B_20260729.mp4") `
        -stream_loop 1 -i (Join-Path $sourceDir "BQ001_WideToeBox_ProductProof_V2_20260728.mp4") `
        -filter_complex "[0:v]eq=contrast=1.02:saturation=0.97:brightness=0.004,subtitles='captions_v7_cn.ass'[v];[1:a]atrim=0:12.1,asetpts=PTS-STARTPTS,volume=1.06,highpass=f=75,lowpass=f=13000,afade=t=in:st=0:d=0.03,afade=t=out:st=11.86:d=0.17[voice];[2:a]atrim=0:15.5,asetpts=PTS-STARTPTS,volume=0.07,afade=t=in:st=0:d=0.5,afade=t=out:st=14.5:d=1.0[music];[voice][music]amix=inputs=2:duration=longest:normalize=0,loudnorm=I=-14:TP=-1:LRA=7[a]" `
        -map "[v]" -map "[a]" -t 15.5 `
        -c:v libx264 -preset slow -crf 17 -profile:v high -level 4.1 -pix_fmt yuv420p `
        -c:a aac -b:a 192k -ar 48000 -movflags +faststart `
        "final_v7_cn.mp4"
    if ($LASTEXITCODE -ne 0) { throw "Final render failed." }
}
finally {
    Pop-Location
}
