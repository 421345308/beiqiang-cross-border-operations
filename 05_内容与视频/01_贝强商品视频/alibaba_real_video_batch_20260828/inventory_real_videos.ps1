param(
    [string]$Workspace = "C:\Users\spq\Desktop\贝强"
)

$ErrorActionPreference = "Stop"
$ffprobe = "C:\Users\spq\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffprobe.exe"
$project = Join-Path $Workspace "05_内容与视频\01_贝强商品视频\alibaba_real_video_batch_20260828"
$outDir = Join-Path $project "inventory"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$searchRoots = @(
    (Join-Path $Workspace "01_产品资产\01_原始数据包"),
    (Join-Path $Workspace "01_产品资产\02_已整理商品包")
) | Where-Object { Test-Path -LiteralPath $_ }

$extensions = @(".mp4", ".mov", ".m4v", ".avi", ".mkv")
$files = foreach ($root in $searchRoots) {
    Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object {
        $extensions -contains $_.Extension.ToLowerInvariant()
    }
}

$rows = foreach ($file in ($files | Sort-Object FullName -Unique)) {
    $skuMatch = [regex]::Match($file.FullName, "BQ\s*[-_]?\s*(\d{1,3})", "IgnoreCase")
    $sku = if ($skuMatch.Success) { "BQ{0:D3}" -f [int]$skuMatch.Groups[1].Value } else { "UNMAPPED" }

    $probeText = & $ffprobe -v error -show_entries format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate -of json -- "$($file.FullName)"
    $probe = $probeText | ConvertFrom-Json
    $video = $probe.streams | Where-Object { $_.codec_type -eq "video" } | Select-Object -First 1
    $audio = $probe.streams | Where-Object { $_.codec_type -eq "audio" } | Select-Object -First 1
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    $ratio = if ($video.width -and $video.height) { [math]::Round([double]$video.width / [double]$video.height, 3) } else { $null }
    $orientation = if (-not $video.width) { "unknown" } elseif ($ratio -gt 1.1) { "landscape" } elseif ($ratio -lt 0.9) { "portrait" } else { "square" }

    [pscustomobject]@{
        sku = $sku
        file_name = $file.Name
        full_path = $file.FullName
        duration_seconds = [math]::Round([double]$probe.format.duration, 3)
        width = $video.width
        height = $video.height
        orientation = $orientation
        video_codec = $video.codec_name
        frame_rate = $video.r_frame_rate
        has_audio = [bool]$audio
        audio_codec = if ($audio) { $audio.codec_name } else { "" }
        bytes = [int64]$probe.format.size
        sha256 = $hash
    }
}

$rows | Export-Csv -LiteralPath (Join-Path $outDir "real_product_video_inventory.csv") -NoTypeInformation -Encoding UTF8
$rows | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $outDir "real_product_video_inventory.json") -Encoding UTF8

$uniqueRows = $rows | Group-Object sha256 | ForEach-Object { $_.Group | Select-Object -First 1 }
$summary = $uniqueRows | Group-Object sku | Sort-Object Name | ForEach-Object {
    [pscustomobject]@{
        sku = $_.Name
        unique_video_count = $_.Count
        landscape = ($_.Group | Where-Object orientation -eq "landscape").Count
        square = ($_.Group | Where-Object orientation -eq "square").Count
        portrait = ($_.Group | Where-Object orientation -eq "portrait").Count
        total_duration_seconds = [math]::Round((($_.Group | Measure-Object duration_seconds -Sum).Sum), 2)
    }
}
$summary | Export-Csv -LiteralPath (Join-Path $outDir "real_product_video_summary.csv") -NoTypeInformation -Encoding UTF8

[pscustomobject]@{
    files = $rows.Count
    unique_files = $uniqueRows.Count
    mapped_skus = ($uniqueRows | Where-Object sku -ne "UNMAPPED" | Select-Object -ExpandProperty sku -Unique).Count
    output = $outDir
} | ConvertTo-Json
