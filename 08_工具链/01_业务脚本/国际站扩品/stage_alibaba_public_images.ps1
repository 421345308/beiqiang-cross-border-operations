param(
    [Parameter(Mandatory = $true)]
    [string]$RawBatchOutput,

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh -ErrorAction Stop).Source
    & $pwsh -NoProfile -File $PSCommandPath -RawBatchOutput $RawBatchOutput -OutputDirectory $OutputDirectory
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'
$rawPath = (Resolve-Path $RawBatchOutput).Path
$outputPath = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputDirectory))
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

function Resolve-CdnUrl([string]$imageUrl) {
    if ([string]::IsNullOrWhiteSpace($imageUrl)) { return $null }
    if ($imageUrl -match '^https://') { return $imageUrl }
    return 'https://sc04.alicdn.com/kf/' + $imageUrl.TrimStart('/')
}

function Add-ImageEntry(
    [System.Collections.Generic.List[object]]$entries,
    [string]$sku,
    [string]$role,
    [int]$index,
    [string]$imageUrl
) {
    $url = Resolve-CdnUrl $imageUrl
    if (-not $url) { return }
    $extension = [System.IO.Path]::GetExtension(($url -split '[?#]')[0])
    if ([string]::IsNullOrWhiteSpace($extension)) { $extension = '.jpg' }
    $safeRole = $role -replace '[^a-zA-Z0-9_-]', '_'
    $fileName = '{0:D2}_{1}_{2:D2}{3}' -f $entries.Count, $safeRole, $index, $extension.ToLowerInvariant()
    $entries.Add([pscustomobject]@{
        sku = $sku
        role = $role
        index = $index
        url = $url
        fileName = $fileName
    })
}

$payload = Get-Content -LiteralPath $rawPath -Raw | ConvertFrom-Json
$manifest = [System.Collections.Generic.List[object]]::new()

foreach ($step in $payload.data.results) {
    if (-not $step.success) { continue }
    $sku = $step.name.ToUpperInvariant()
    $query = $step.output.data.productQueryResult | ConvertFrom-Json
    $entries = [System.Collections.Generic.List[object]]::new()

    $i = 0
    foreach ($image in @($query.mediaInfoDTO.generalImages)) {
        Add-ImageEntry $entries $sku 'main' $i $image.imageUrl
        $i++
    }
    $i = 0
    foreach ($image in @($query.mediaInfoDTO.descriptionImages)) {
        Add-ImageEntry $entries $sku 'detail' $i $image.imageUrl
        $i++
    }
    $i = 0
    foreach ($image in @($query.mediaInfoDTO.companyImages)) {
        Add-ImageEntry $entries $sku 'company' $i $image.imageUrl
        $i++
    }

    $skuImageUrls = @($query.skuList |
        ForEach-Object {
            $binding = $_.featureMap.icbu_sku_property_img
            if (-not [string]::IsNullOrWhiteSpace($binding)) {
                ($binding -split '\*')[-1]
            }
        } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Sort-Object -Unique)
    for ($skuImageIndex = 0; $skuImageIndex -lt $skuImageUrls.Count; $skuImageIndex++) {
        Add-ImageEntry $entries $sku 'sku' $skuImageIndex $skuImageUrls[$skuImageIndex]
    }

    $skuDirectory = Join-Path $outputPath $sku
    New-Item -ItemType Directory -Force -Path $skuDirectory | Out-Null
    foreach ($entry in $entries) {
        $destination = Join-Path $skuDirectory $entry.fileName
        if (-not (Test-Path -LiteralPath $destination)) {
            Invoke-WebRequest -Uri $entry.url -OutFile $destination -UseBasicParsing
        }
        $manifest.Add([pscustomobject]@{
            sku = $sku
            role = $entry.role
            index = $entry.index
            url = $entry.url
            path = $destination
            bytes = (Get-Item -LiteralPath $destination).Length
        })
    }
}

$manifestPath = Join-Path $outputPath 'manifest.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding utf8
[pscustomobject]@{
    outputDirectory = $outputPath
    products = @($manifest.sku | Sort-Object -Unique).Count
    images = $manifest.Count
    manifest = $manifestPath
} | ConvertTo-Json -Depth 4
