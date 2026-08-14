param(
    [string]$SourceDirectory,
    [string]$OutputDirectory,
    [int]$Columns = 4,
    [int]$Rows = 3
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

if ([string]::IsNullOrWhiteSpace($SourceDirectory)) {
    $workspace = Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent
    $SourceDirectory = Join-Path $workspace '01_产品资产\01_原始数据包\待审_搜鞋网_2026-08-14\_候选主图'
}
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $SourceDirectory '_联系表'
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$files = @(Get-ChildItem -LiteralPath $SourceDirectory -File |
    Where-Object { $_.Extension -match '^\.(jpg|jpeg|png|webp)$' } |
    Sort-Object BaseName)

$cellWidth = 320
$cellHeight = 260
$labelHeight = 34
$perSheet = $Columns * $Rows
$sheetWidth = $Columns * $cellWidth
$sheetHeight = $Rows * $cellHeight
$font = New-Object System.Drawing.Font('Arial', 16, [System.Drawing.FontStyle]::Bold)
$labelBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(28, 28, 28))
$textBrush = [System.Drawing.Brushes]::White
$borderPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(205, 205, 205), 1)

try {
    for ($offset = 0; $offset -lt $files.Count; $offset += $perSheet) {
        $sheetIndex = [int]($offset / $perSheet) + 1
        $bitmap = New-Object System.Drawing.Bitmap($sheetWidth, $sheetHeight)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.Clear([System.Drawing.Color]::White)
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality

            $pageFiles = @($files | Select-Object -Skip $offset -First $perSheet)
            for ($index = 0; $index -lt $pageFiles.Count; $index++) {
                $file = $pageFiles[$index]
                $column = $index % $Columns
                $row = [int][Math]::Floor($index / $Columns)
                $x = $column * $cellWidth
                $y = $row * $cellHeight

                $graphics.DrawRectangle($borderPen, $x, $y, $cellWidth - 1, $cellHeight - 1)
                $image = [System.Drawing.Image]::FromFile($file.FullName)
                try {
                    $availableWidth = $cellWidth - 16
                    $availableHeight = $cellHeight - $labelHeight - 16
                    $scale = [Math]::Min($availableWidth / $image.Width, $availableHeight / $image.Height)
                    $drawWidth = [int]($image.Width * $scale)
                    $drawHeight = [int]($image.Height * $scale)
                    $drawX = $x + [int](($cellWidth - $drawWidth) / 2)
                    $drawY = $y + 8 + [int](($availableHeight - $drawHeight) / 2)
                    $graphics.DrawImage($image, $drawX, $drawY, $drawWidth, $drawHeight)
                }
                finally {
                    $image.Dispose()
                }

                $labelY = $y + $cellHeight - $labelHeight
                $graphics.FillRectangle($labelBrush, $x, $labelY, $cellWidth, $labelHeight)
                $graphics.DrawString($file.BaseName, $font, $textBrush, $x + 8, $labelY + 5)
            }

            $output = Join-Path $OutputDirectory ('候选主图联系表_{0:D2}.jpg' -f $sheetIndex)
            $bitmap.Save($output, [System.Drawing.Imaging.ImageFormat]::Jpeg)
            Write-Output $output
        }
        finally {
            $graphics.Dispose()
            $bitmap.Dispose()
        }
    }
}
finally {
    $font.Dispose()
    $labelBrush.Dispose()
    $borderPen.Dispose()
}
