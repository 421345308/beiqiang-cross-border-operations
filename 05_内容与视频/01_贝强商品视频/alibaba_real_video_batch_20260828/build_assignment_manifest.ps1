param(
    [string]$Workspace = "C:\Users\spq\Desktop\贝强"
)

$ErrorActionPreference = "Stop"
$project = Join-Path $Workspace "05_内容与视频\01_贝强商品视频\alibaba_real_video_batch_20260828"
$finalDir = Join-Path $project "edit\final"
$factoryMaster = Join-Path $project "edit\Beiqiang_Factory_Full_Clean_Actual_Footage_20260828.mp4"
$combinedSkus = Get-ChildItem -LiteralPath $finalDir -Filter "BQ*_Real_Product_And_Full_Factory_20260828.mp4" -File |
    ForEach-Object { [regex]::Match($_.Name, "BQ\d{3}").Value }

$manifest = 1..56 | ForEach-Object {
    $sku = "BQ{0:D3}" -f $_
    $combined = Join-Path $finalDir ("{0}_Real_Product_And_Full_Factory_20260828.mp4" -f $sku)
    if ($combinedSkus -contains $sku) {
        [pscustomobject]@{
            sku = $sku
            assignment = "real product footage + full factory footage"
            video_path = $combined
            status = "generated"
            note = "Real moving product footage; no slideshow."
        }
    } else {
        $reason = if ($sku -eq "BQ029") { "Source product video contains embedded Chinese retail captions." } else { "No verified real product video in the current package." }
        [pscustomobject]@{
            sku = $sku
            assignment = "full factory footage"
            video_path = $factoryMaster
            status = "reuse universal factory film"
            note = $reason
        }
    }
}

$manifest | Export-Csv -LiteralPath (Join-Path $project "product_video_assignment_56_skus.csv") -NoTypeInformation -Encoding UTF8
$manifest | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $project "product_video_assignment_56_skus.json") -Encoding UTF8
$manifest | Group-Object assignment | Select-Object Name,Count | Format-Table -AutoSize | Out-String
