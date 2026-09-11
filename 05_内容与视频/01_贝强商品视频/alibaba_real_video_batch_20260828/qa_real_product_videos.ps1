param(
    [string]$Workspace = "C:\Users\spq\Desktop\贝强"
)

$ErrorActionPreference = "Stop"
$ffprobe = "C:\Users\spq\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffprobe.exe"
$project = Join-Path $Workspace "05_内容与视频\01_贝强商品视频\alibaba_real_video_batch_20260828"
$finalDir = Join-Path $project "edit\final"
$reportPath = Join-Path $project "qa_report.csv"

$rows = foreach ($file in (Get-ChildItem -LiteralPath $finalDir -Filter "BQ*_Real_Product_And_Full_Factory_20260828.mp4" -File | Sort-Object Name)) {
    $probeText = & $ffprobe -v error -show_entries format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate -of json -- "$($file.FullName)"
    $probe = $probeText | ConvertFrom-Json
    $video = $probe.streams | Where-Object codec_type -eq "video" | Select-Object -First 1
    $audio = $probe.streams | Where-Object codec_type -eq "audio" | Select-Object -First 1
    $sku = [regex]::Match($file.Name, "BQ\d{3}").Value
    $duration = [math]::Round([double]$probe.format.duration, 3)
    $issues = @()
    if ($video.codec_name -ne "h264") { $issues += "video codec is not H.264" }
    if ($video.width -ne 1920 -or $video.height -ne 1080) { $issues += "resolution is not 1920x1080" }
    if ($video.r_frame_rate -ne "30/1") { $issues += "frame rate is not 30 fps" }
    if (-not $audio -or $audio.codec_name -ne "aac") { $issues += "AAC audio track missing" }
    if ($duration -lt 90 -or $duration -gt 110) { $issues += "unexpected duration" }
    if ([int64]$probe.format.size -le 0) { $issues += "empty file" }
    [pscustomobject]@{
        sku = $sku
        file = $file.FullName
        duration_seconds = $duration
        width = $video.width
        height = $video.height
        fps = $video.r_frame_rate
        video_codec = $video.codec_name
        audio_codec = if ($audio) { $audio.codec_name } else { "" }
        size_mb = [math]::Round([int64]$probe.format.size / 1MB, 2)
        qa_status = if ($issues.Count -eq 0) { "PASS" } else { "FAIL" }
        issues = $issues -join "; "
    }
}

$rows | Export-Csv -LiteralPath $reportPath -NoTypeInformation -Encoding UTF8
$rows | Group-Object qa_status | Select-Object Name,Count | Format-Table -AutoSize | Out-String
