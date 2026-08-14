param(
    [ValidateSet('Inventory', 'CandidateCovers', 'SelectedPackages')]
    [string]$Mode = 'Inventory',
    [string[]]$SelectedArtno = @()
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Net.Http

$workspace = Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent
$rawRoot = Join-Path $workspace '01_产品资产\01_原始数据包'
$projectRoot = Join-Path $workspace '02_Alibaba运营\05_扩品工程'
$dataRoot = Join-Path $projectRoot '数据'
$downloadRoot = Join-Path $rawRoot '待审_搜鞋网_2026-08-14'
$coverRoot = Join-Path $downloadRoot '_候选主图'
$inventoryCsv = Join-Path $dataRoot '搜鞋网贝强工厂店在线商品_2026-08-14.csv'
$candidateCsv = Join-Path $dataRoot '搜鞋网待去重候选_2026-08-14.csv'

New-Item -ItemType Directory -Force -Path $dataRoot, $downloadRoot, $coverRoot | Out-Null

$headers = @{
    'User-Agent' = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/127 Safari/537.36'
}

function Get-RemoteText {
    param([Parameter(Mandatory = $true)][string]$Uri)

    $lastError = $null
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            return (Invoke-WebRequest -UseBasicParsing -Uri $Uri -Headers $headers -TimeoutSec 40).Content
        }
        catch {
            $lastError = $_
            if ($attempt -lt 3) { Start-Sleep -Seconds (2 * $attempt) }
        }
    }
    throw "无法读取 $Uri：$($lastError.Exception.Message)"
}

function Convert-HtmlText {
    param([AllowEmptyString()][string]$Text)

    if ($null -eq $Text) { return '' }
    $decoded = [System.Net.WebUtility]::HtmlDecode($Text)
    return ([regex]::Replace($decoded, '<[^>]+>', '')).Trim()
}

function Get-TagValues {
    param(
        [string]$Html,
        [string]$ElementId
    )

    $block = [regex]::Match(
        $Html,
        '<p\s+id="' + [regex]::Escape($ElementId) + '">(?<body>.*?)</p>',
        [Text.RegularExpressions.RegexOptions]::Singleline
    )
    if (-not $block.Success) { return @() }
    return @([regex]::Matches($block.Groups['body'].Value, '<em>(?<v>.*?)</em>', [Text.RegularExpressions.RegexOptions]::Singleline) |
        ForEach-Object { Convert-HtmlText $_.Groups['v'].Value })
}

function Get-DetailMetadata {
    param([Parameter(Mandatory = $true)]$Item)

    $detailUrl = "https://bqgcd.sooxie.com/detail/$($Item.id)"
    $html = Get-RemoteText -Uri $detailUrl

    $titleMatch = [regex]::Match($html, '<div class="shop-title"><h2>(?<v>.*?)</h2>', [Text.RegularExpressions.RegexOptions]::Singleline)
    $artMatch = [regex]::Match($html, '货号：<u>(?<v>.*?)</u>', [Text.RegularExpressions.RegexOptions]::Singleline)
    $priceMatch = [regex]::Match($html, '价格：<span class="meri-price">(?<v>.*?)</span>', [Text.RegularExpressions.RegexOptions]::Singleline)
    $dateMatch = [regex]::Match($html, '上架时间</span></div><div class="sc-text"><p>(?<v>.*?)</p>', [Text.RegularExpressions.RegexOptions]::Singleline)
    $pidMatch = [regex]::Match($html, '<input name="pid" type="hidden" value="(?<v>\d+)"')

    $detailsBlock = [regex]::Match(
        $html,
        '<div class="shop-photo-list" id="details">(?<body>.*?)</div>\s*</div>',
        [Text.RegularExpressions.RegexOptions]::Singleline
    )
    $detailImages = @()
    if ($detailsBlock.Success) {
        $detailImages = @([regex]::Matches($detailsBlock.Groups['body'].Value, '(?:data-url|src)="(?<u>https://[^" ]+)"') |
            ForEach-Object { [System.Net.WebUtility]::HtmlDecode($_.Groups['u'].Value) } |
            Where-Object { $_ -match 'xiecdn\.com/' } |
            Select-Object -Unique)
    }

    [pscustomobject]@{
        source_status = $Item.source_status
        artno = if ($artMatch.Success) { Convert-HtmlText $artMatch.Groups['v'].Value } else { $Item.artno }
        sooxie_id = [int]$Item.id
        title_cn = if ($titleMatch.Success) { Convert-HtmlText $titleMatch.Groups['v'].Value } else { $Item.title }
        price_cny = if ($priceMatch.Success) { Convert-HtmlText $priceMatch.Groups['v'].Value } else { $Item.price }
        colors = (Get-TagValues -Html $html -ElementId 'color') -join ';'
        sizes = (Get-TagValues -Html $html -ElementId 'size') -join ';'
        listed_date = if ($dateMatch.Success) { Convert-HtmlText $dateMatch.Groups['v'].Value } else { '' }
        detail_url = $detailUrl
        cover_url = $Item.picture
        detail_image_count = $detailImages.Count
        detail_image_urls = $detailImages -join ';'
        download_pid = if ($pidMatch.Success) { $pidMatch.Groups['v'].Value } else { '' }
        exact_local_model_match = $Item.exact_local_model_match
        review_status = if ($Item.exact_local_model_match) { '本地货号已存在' } else { '待结构与图片去重' }
        next_action = if ($Item.exact_local_model_match) { '核验国际站状态' } else { '核验是否为独立鞋型或仅为配色/加绒/别名变体' }
    }
}

function Save-RemoteFile {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    $cleanUri = $Uri.Trim()
    Invoke-WebRequest -UseBasicParsing -Uri $cleanUri -Headers $headers -TimeoutSec 60 -OutFile $Destination
    $bytes = [IO.File]::ReadAllBytes($Destination)
    $isWebp = $bytes.Length -ge 12 -and
        [Text.Encoding]::ASCII.GetString($bytes, 0, 4) -eq 'RIFF' -and
        [Text.Encoding]::ASCII.GetString($bytes, 8, 4) -eq 'WEBP'
    if ($isWebp -and [IO.Path]::GetExtension($Destination) -ine '.webp') {
        $webpDestination = [IO.Path]::ChangeExtension($Destination, '.webp')
        Move-Item -LiteralPath $Destination -Destination $webpDestination -Force
    }
}

function Save-RemoteFilesParallel {
    param(
        [Parameter(Mandatory = $true)][array]$Entries,
        [int]$MaxParallel = 4
    )

    $handler = New-Object System.Net.Http.HttpClientHandler
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(60)
    $client.DefaultRequestHeaders.UserAgent.ParseAdd($headers['User-Agent'])

    try {
        for ($offset = 0; $offset -lt $Entries.Count; $offset += $MaxParallel) {
            $batch = @($Entries | Select-Object -Skip $offset -First $MaxParallel)
            $requests = @()
            foreach ($entry in $batch) {
                if (Test-Path -LiteralPath $entry.Destination) { continue }
                $requests += [pscustomobject]@{
                    Entry = $entry
                    Task = $client.GetByteArrayAsync($entry.PrimaryUri)
                }
            }

            foreach ($request in $requests) {
                try {
                    $bytes = $request.Task.GetAwaiter().GetResult()
                }
                catch {
                    if ([string]::IsNullOrWhiteSpace($request.Entry.FallbackUri)) { throw }
                    $bytes = $client.GetByteArrayAsync($request.Entry.FallbackUri).GetAwaiter().GetResult()
                }
                $destination = $request.Entry.Destination
                $isWebp = $bytes.Length -ge 12 -and
                    [Text.Encoding]::ASCII.GetString($bytes, 0, 4) -eq 'RIFF' -and
                    [Text.Encoding]::ASCII.GetString($bytes, 8, 4) -eq 'WEBP'
                if ($isWebp) { $destination = [IO.Path]::ChangeExtension($destination, '.webp') }
                [IO.File]::WriteAllBytes($destination, $bytes)
            }
        }
    }
    finally {
        $client.Dispose()
        $handler.Dispose()
    }
}

$indexHtml = Get-RemoteText -Uri 'https://bqgcd.sooxie.com/?state=5'
$itemPattern = '<li>\s*<div class="asx-picture">\s*<a[^>]+href="https://bqgcd\.sooxie\.com/detail/(?<id>\d+)"><img[^>]+data-url="(?<pic>[^"]+)"[^>]*></a>\s*<h4>(?<art>[^<]+)</h4>\s*</div>\s*<em><a[^>]+>(?<title>[^<]+)</a></em>\s*<u>(?<price>[0-9.]+)</u>'
$page1 = @([regex]::Matches($indexHtml, $itemPattern, [Text.RegularExpressions.RegexOptions]::Singleline) | ForEach-Object {
    [pscustomobject]@{
        id = [int]$_.Groups['id'].Value
        artno = (Convert-HtmlText $_.Groups['art'].Value)
        title = (Convert-HtmlText $_.Groups['title'].Value)
        price = [decimal]$_.Groups['price'].Value
        picture = [System.Net.WebUtility]::HtmlDecode($_.Groups['pic'].Value)
    }
})

$page2Json = Get-RemoteText -Uri 'https://sooxie.com/api/Detail/ProList?url=bqgcd&sort=5&min=&max=&page=2'
$page2 = @((ConvertFrom-Json $page2Json).data)
$allItems = @($page1) + @($page2)
$allItems = @($allItems | Sort-Object id -Unique)

$localModels = @()
Get-ChildItem -LiteralPath $rawRoot -Directory | ForEach-Object {
    if ($_.Name -match '^已整理_BQ\d{3}_([^_]+)') { $localModels += $Matches[1] }
}

foreach ($item in $allItems) {
    $item | Add-Member -NotePropertyName exact_local_model_match -NotePropertyValue ($localModels -contains $item.artno) -Force
    $item | Add-Member -NotePropertyName source_status -NotePropertyValue '搜鞋网在线' -Force
}

$candidateItems = @($allItems | Where-Object { -not $_.exact_local_model_match })

if ($Mode -eq 'Inventory') {
    $allRows = foreach ($item in $allItems) { Get-DetailMetadata -Item $item }
    $allRows | Sort-Object artno | Export-Csv -LiteralPath $inventoryCsv -NoTypeInformation -Encoding UTF8
    $allRows | Where-Object { -not $_.exact_local_model_match } | Sort-Object artno |
        Export-Csv -LiteralPath $candidateCsv -NoTypeInformation -Encoding UTF8
    Write-Output "已写入在线商品清单：$inventoryCsv"
    Write-Output "已写入待去重候选：$candidateCsv"
    Write-Output "在线商品 $($allRows.Count) 款；货号精确匹配 $(@($allRows | Where-Object exact_local_model_match).Count) 款；候选缺口 $(@($allRows | Where-Object { -not $_.exact_local_model_match }).Count) 款。"
    exit 0
}

if (-not (Test-Path -LiteralPath $candidateCsv)) {
    throw "缺少候选清单，请先运行 -Mode Inventory：$candidateCsv"
}

$candidateRows = @(Import-Csv -LiteralPath $candidateCsv)

if ($Mode -eq 'CandidateCovers') {
    foreach ($row in $candidateRows) {
        $ext = [IO.Path]::GetExtension(($row.cover_url -split '!')[0])
        if ([string]::IsNullOrWhiteSpace($ext)) { $ext = '.jpg' }
        $destination = Join-Path $coverRoot ($row.artno + $ext.ToLowerInvariant())
        if (-not (Test-Path -LiteralPath $destination)) {
            Save-RemoteFile -Uri $row.cover_url -Destination $destination
        }
    }
    Write-Output "已下载 $($candidateRows.Count) 款候选主图：$coverRoot"
    exit 0
}

if ($SelectedArtno.Count -eq 0) {
    throw 'SelectedPackages 模式必须通过 -SelectedArtno 指定至少一个货号。'
}

$selected = @($candidateRows | Where-Object { $SelectedArtno -contains $_.artno })
$missing = @($SelectedArtno | Where-Object { $_ -notin $selected.artno })
if ($missing.Count -gt 0) { throw "候选清单中找不到货号：$($missing -join ', ')" }

foreach ($row in $selected) {
    $safeArtno = $row.artno -replace '[\\/:*?"<>|]', '_'
    $packageDir = Join-Path $downloadRoot $safeArtno
    $imageDir = Join-Path $packageDir '原图'
    New-Item -ItemType Directory -Force -Path $packageDir, $imageDir | Out-Null

    $metadataPath = Join-Path $packageDir 'source.json'
    $row | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $metadataPath -Encoding UTF8

    $urls = @($row.detail_image_urls -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $downloadEntries = @()
    for ($index = 0; $index -lt $urls.Count; $index++) {
        $rawUrl = $urls[$index]
        $baseUrl = $rawUrl -replace '![^!/?]+$', ''
        $ext = [IO.Path]::GetExtension(($baseUrl -split '\?')[0])
        if ([string]::IsNullOrWhiteSpace($ext)) { $ext = '.jpg' }
        $destination = Join-Path $imageDir ('{0:D2}{1}' -f ($index + 1), $ext.ToLowerInvariant())
        if (-not (Test-Path -LiteralPath $destination)) {
            $downloadEntries += [pscustomobject]@{
                PrimaryUri = $baseUrl
                FallbackUri = $rawUrl
                Destination = $destination
            }
        }
    }
    if ($downloadEntries.Count -gt 0) {
        Save-RemoteFilesParallel -Entries $downloadEntries -MaxParallel 4
    }
    Write-Output "已完成数据包：$($row.artno)（$($urls.Count) 张详情图）"
}
