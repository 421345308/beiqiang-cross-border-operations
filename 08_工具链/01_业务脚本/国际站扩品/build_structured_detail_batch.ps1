param(
    [Parameter(Mandatory = $true)]
    [string]$Plan,

    [Parameter(Mandatory = $true)]
    [string]$Output,

    [string]$CurrentDraft
)

$ErrorActionPreference = 'Stop'
$items = Get-Content -LiteralPath $Plan -Raw | ConvertFrom-Json

$companyImages = @(
    [ordered]@{ imageIndex = 0; imageSetId = '400'; url = 'https://sc04.alicdn.com/kf/Sf587c854711748af9759e77ce5aeb03c3/286385890/Sf587c854711748af9759e77ce5aeb03c3.png' },
    [ordered]@{ imageIndex = 1; imageSetId = '450'; url = 'https://sc04.alicdn.com/kf/Sfea34bbd56ae4d0583aa855838eb1454F/286385890/Sfea34bbd56ae4d0583aa855838eb1454F.png' },
    [ordered]@{ imageIndex = 2; imageSetId = '500'; url = 'https://sc04.alicdn.com/kf/Sdc4e18f098e142b797df687e8befbfa14/286385890/Sdc4e18f098e142b797df687e8befbfa14.png' },
    [ordered]@{ imageIndex = 3; imageSetId = '600'; url = 'https://sc04.alicdn.com/kf/Sc1dc6ec7d435404db6a31c6938a734a0g/286385890/Sc1dc6ec7d435404db6a31c6938a734a0g.png' },
    [ordered]@{ imageIndex = 4; imageSetId = '700'; url = 'https://sc04.alicdn.com/kf/S2a3af5690d524680824086ad8419dbc9G/286385890/S2a3af5690d524680824086ad8419dbc9G.png' }
)

$companyDesc = 'Quanzhou Beiqiang Footwear & Apparel Co., Ltd. is a footwear factory supplier located in Quanzhou, Fujian, China. We supply casual walking shoes, lightweight slip-on shoes and related footwear for overseas B2B buyers. Product specifications, colors, size ratios, packing and customization requirements are confirmed according to the current style and order details.'

$faqAnswers = @(
    'We are a footwear factory supplier located in Quanzhou, Fujian, China, serving overseas B2B buyers.',
    'The current store baseline starts from 2 pairs. The applicable quantity, price and production arrangement are confirmed according to the selected style and order requirements.',
    'Mixed colors and sizes can be discussed, subject to current availability, size ratio and production confirmation.',
    'Samples can be discussed for quality checking. Sample price, courier charge and preparation time are quoted separately for the selected style before payment.',
    'The current single-pair package baseline is 34 x 23 x 13 cm and approximately 0.5 kg. Order-specific packing is confirmed before shipment.',
    'Logo, color, size ratio and packaging requirements can be discussed. Please provide your design and target quantity for production review.',
    'The current store baseline is 31 days for 100 pairs. Final lead time depends on style, quantity, materials and customization requirements and is confirmed before order.'
)

$draftBySku = @{}
if ($CurrentDraft) {
    $draftPayload = Get-Content -LiteralPath $CurrentDraft -Raw | ConvertFrom-Json
    foreach ($result in @($draftPayload.data.results)) {
        $draft = $result.output.data
        if ($draft -is [string]) { $draft = $draft | ConvertFrom-Json }
        $draftBySku[[string]$result.name] = $draft
    }
}

$steps = foreach ($item in @($items)) {
    $current = $draftBySku[[string]$item.sku]

    $detailImageOps = @()
    if ($current) {
        foreach ($image in @($current.detail.detailImage)) {
            $detailImageOps += [ordered]@{
                operationType = 'DELETE'
                originalImageUrl = [string]$image.originalImageUrl
                imageIndex = [int]$image.imageIndex
                imageSetId = [string]$image.imageSetId
            }
        }
    }
    for ($index = 0; $index -lt @($item.cdnUrls).Count; $index++) {
        $detailImageOps += [ordered]@{
            operationType = 'ADD'
            newImageUrl = [string]$item.cdnUrls[$index]
            imageIndex = $index
            imageSetId = '350'
        }
    }

    $companyImageOps = @()
    if ($current) {
        foreach ($image in @($current.detail.companyImage)) {
            $companyImageOps += [ordered]@{
                operationType = 'DELETE'
                originalImageUrl = [string]$image.originalImageUrl
                imageIndex = [int]$image.imageIndex
                imageSetId = [string]$image.imageSetId
            }
        }
    }
    foreach ($image in $companyImages) {
        $companyImageOps += [ordered]@{
            operationType = 'ADD'
            newImageUrl = [string]$image.url
            imageIndex = [int]$image.imageIndex
            imageSetId = [string]$image.imageSetId
        }
    }

    $faqOps = for ($index = 0; $index -lt 8; $index++) {
        [ordered]@{
            operationType = 'EDIT'
            sortOrder = $index
            answer = if ($index -eq 7) { [string]$item.finalFaqAnswer } else { [string]$faqAnswers[$index] }
        }
    }

    [ordered]@{
        name = [string]$item.sku
        path = 'icbu.other.product-edit-draft-detail'
        params = [ordered]@{
            productId = [long]$item.productId
            productSellingPoint = [string]$item.productSellingPoint
            detailImage = @($detailImageOps)
            companyImage = @($companyImageOps)
            companyDesc = $companyDesc
            faqs = @($faqOps)
        }
    }
}

$parent = Split-Path -Parent ([System.IO.Path]::GetFullPath($Output))
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
[ordered]@{ steps = @($steps) } | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $Output -Encoding utf8
