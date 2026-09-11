param(
    [string]$Workspace = "C:\Users\spq\Desktop\贝强"
)

$ErrorActionPreference = "Stop"
$ffmpeg = "C:\Users\spq\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe"
$project = Join-Path $Workspace "05_内容与视频\01_贝强商品视频\alibaba_real_video_batch_20260828"
$inventory = Join-Path $project "inventory\selected_candidates.csv"
$outDir = Join-Path $project "review_sheets"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

foreach ($row in (Import-Csv -LiteralPath $inventory)) {
    $interval = [math]::Max(1, [double]$row.duration_seconds / 4.0)
    $output = Join-Path $outDir ("{0}_candidate.jpg" -f $row.sku)
    & $ffmpeg -hide_banner -loglevel error -y -i "$($row.full_path)" -vf "fps=1/$interval,scale=360:360:force_original_aspect_ratio=decrease,pad=360:360:(ow-iw)/2:(oh-ih)/2:white,tile=4x1" -frames:v 1 "$output"
    if ($LASTEXITCODE -ne 0) { throw "Contact sheet failed: $($row.full_path)" }
}

$factorySources = @(
    @{ Name = "factory_60s_full"; Path = "D:\下载\泉州贝强鞋服有限公司-有字幕.mov"; Interval = 5 },
    @{ Name = "factory_180s_material"; Path = "D:\下载\素材.mp4"; Interval = 15 }
)
foreach ($source in $factorySources) {
    if (-not (Test-Path -LiteralPath $source.Path)) { continue }
    $output = Join-Path $outDir ("{0}.jpg" -f $source.Name)
    & $ffmpeg -hide_banner -loglevel error -y -i "$($source.Path)" -vf "fps=1/$($source.Interval),scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2:black,tile=4x3" -frames:v 1 "$output"
    if ($LASTEXITCODE -ne 0) { throw "Factory contact sheet failed: $($source.Path)" }
}

$finalDir = Join-Path $project "edit\final"
foreach ($file in (Get-ChildItem -LiteralPath $finalDir -Filter "BQ*_Real_Product_And_Full_Factory_20260828.mp4" -File)) {
    $sku = [regex]::Match($file.Name, "BQ\d{3}").Value
    $output = Join-Path $outDir ("{0}_final.jpg" -f $sku)
    & $ffmpeg -hide_banner -loglevel error -y -i "$($file.FullName)" -vf "fps=1/25,scale=480:270,tile=4x1" -frames:v 1 "$output"
    if ($LASTEXITCODE -ne 0) { throw "Final review sheet failed: $($file.FullName)" }
}

Write-Output $outDir
