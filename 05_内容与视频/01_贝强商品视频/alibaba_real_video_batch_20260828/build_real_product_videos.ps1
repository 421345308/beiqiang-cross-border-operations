param(
    [string]$Workspace = "C:\Users\spq\Desktop\贝强",
    [string]$OnlySku = "",
    [string]$StartSku = "",
    [switch]$Overwrite
)

$ErrorActionPreference = "Stop"
$ffmpeg = "C:\Users\spq\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe"
$project = Join-Path $Workspace "05_内容与视频\01_贝强商品视频\alibaba_real_video_batch_20260828"
$inventory = Join-Path $project "inventory\selected_candidates.csv"
$editDir = Join-Path $project "edit"
$finalDir = Join-Path $editDir "final"
$factorySource = "D:\下载\泉州贝强鞋服有限公司-有字幕.mov"
$factoryMaterial = "D:\下载\素材.mp4"
$factoryMaster = Join-Path $editDir "Beiqiang_Factory_Full_Clean_Actual_Footage_20260828.mp4"
New-Item -ItemType Directory -Force -Path $finalDir | Out-Null

if (-not (Test-Path -LiteralPath $factoryMaster)) {
    # Keep all useful factory proof, remove static splash screens and third-party branded cartons.
    # Replace the branded ending with clean material-storage and open-box packing footage.
    $factoryFilter = @"
[0:v]trim=start=3:end=51,setpts=PTS-STARTPTS,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,fps=30,format=yuv420p[v0];
[0:a]atrim=start=3:end=51,asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a0];
[1:v]trim=start=25:end=40,setpts=PTS-STARTPTS,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,fps=30,format=yuv420p[v1];
[1:a]atrim=start=25:end=40,asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a1];
[1:v]trim=start=125:end=130,setpts=PTS-STARTPTS,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,fps=30,format=yuv420p[v2];
[1:a]atrim=start=125:end=130,asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a2];
[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]
"@
    & $ffmpeg -hide_banner -loglevel error -y -i "$factorySource" -i "$factoryMaterial" `
        -filter_complex $factoryFilter -map "[v]" -map "[a]" `
        -c:v libx264 -preset veryfast -crf 21 -c:a aac -b:a 160k -movflags +faststart "$factoryMaster"
    if ($LASTEXITCODE -ne 0) { throw "Factory master generation failed." }
}

$rows = Import-Csv -LiteralPath $inventory
if ($OnlySku) { $rows = $rows | Where-Object sku -eq $OnlySku }
if ($StartSku) { $rows = $rows | Where-Object { [int]$_.sku.Substring(2) -ge [int]$StartSku.Substring(2) } }
$blockedProductFootage = @("BQ029") # Embedded Chinese retail captions; use the universal factory film instead.
$rows = $rows | Where-Object { $blockedProductFootage -notcontains $_.sku }

foreach ($row in $rows) {
    $output = Join-Path $finalDir ("{0}_Real_Product_And_Full_Factory_20260828.mp4" -f $row.sku)
    if ((Test-Path -LiteralPath $output) -and -not $OnlySku -and -not $Overwrite) {
        Write-Output "SKIP_EXISTING $output"
        continue
    }
    $filter = @"
[0:v]split=2[pbg][pfg];
[pbg]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=20:8[pbg2];
[pfg]scale=1920:1080:force_original_aspect_ratio=decrease[pfg2];
[pbg2][pfg2]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30,format=yuv420p[pv];
[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[pa];
[1:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30,format=yuv420p[fv];
[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[fa];
[pv][pa][fv][fa]concat=n=2:v=1:a=1[v][a]
"@
    & $ffmpeg -hide_banner -loglevel error -y -i "$($row.full_path)" -i "$factoryMaster" `
        -filter_complex $filter -map "[v]" -map "[a]" `
        -c:v libx264 -preset veryfast -crf 22 -c:a aac -b:a 160k -movflags +faststart "$output"
    if ($LASTEXITCODE -ne 0) { throw "Product video failed: $($row.sku)" }
    Write-Output $output
}
