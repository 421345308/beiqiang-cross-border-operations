param(
    [Parameter(Mandatory = $true)]
    [string]$BatchSpec,

    [Parameter(Mandatory = $true)]
    [string]$RawOutput,

    [Parameter(Mandatory = $true)]
    [string]$Report
)

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh -ErrorAction Stop).Source
    & $pwsh -NoProfile -File $PSCommandPath -BatchSpec $BatchSpec -RawOutput $RawOutput -Report $Report
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$workctlRunner = (Get-ChildItem -LiteralPath $workspaceRoot -Recurse -File -Filter 'run_workctl_with_accio_env.py' | Select-Object -First 1).FullName
if (-not $workctlRunner) {
    throw 'run_workctl_with_accio_env.py was not found below the workspace root'
}
$asciiWorkctlRunner = Join-Path $env:TEMP 'beiqiang_run_workctl_with_accio_env.py'
# Windows PowerShell 5 can corrupt a Chinese workspace path when forwarding it
# to some Python installations. The runner is self-contained, so execute an
# ASCII-path temporary copy while keeping all business files in the workspace.
Copy-Item -LiteralPath $workctlRunner -Destination $asciiWorkctlRunner -Force
$batchSpecPath = (Resolve-Path $BatchSpec).Path
$rawOutputPath = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $RawOutput))
$reportPath = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Report))
$asciiBatchSpec = Join-Path $env:TEMP 'beiqiang_public_audit_batch.json'
$asciiRawOutput = Join-Path $env:TEMP 'beiqiang_public_audit_raw.json'
Copy-Item -LiteralPath $batchSpecPath -Destination $asciiBatchSpec -Force

$rawParent = Split-Path -Parent $rawOutputPath
$reportParent = Split-Path -Parent $reportPath
New-Item -ItemType Directory -Force -Path $rawParent, $reportParent | Out-Null

& python $asciiWorkctlRunner batch call --file $asciiBatchSpec --format json --output $asciiRawOutput
if ($LASTEXITCODE -ne 0) {
    throw "Workctl batch call failed with exit code $LASTEXITCODE"
}
Copy-Item -LiteralPath $asciiRawOutput -Destination $rawOutputPath -Force

$payload = Get-Content -LiteralPath $rawOutputPath -Raw | ConvertFrom-Json
if (-not $payload.success) {
    throw 'Workctl batch output reported success=false'
}

$wideCn = [string]([char]0x5BBD) + [char]0x6966
$roomyToeCn = [string]([char]0x5BBD) + [char]0x655E + [char]0x978B + [char]0x5934
$wideRiskPattern = '(?i)wide[ -]?toe|roomy[ -]?toe|' + [regex]::Escape($wideCn) + '|' + [regex]::Escape($roomyToeCn)

$rows = foreach ($step in $payload.data.results) {
    if (-not $step.success) {
        [pscustomobject]@{
            sku = $step.name
            success = $false
            productId = $null
            status = $null
            auditStatus = $null
            pageId = $null
            bodyLength = 0
            bodySha256 = $null
            bodyImageUrls = $null
            uniqueBodyImageUrls = $null
            publicBodyAvailable = $false
            flyknit = $null
            refundDeduct = $null
            unsupportedWideToe = $null
            accioUrl = $null
            nestedAlibabaUrl = $null
            productGalleryMarkers = $null
            companyGalleryMarkers = $null
            error = 'Step failed'
        }
        continue
    }

    $data = @($step.output.data)[0]
    $query = if ($data.productQueryResult -is [string]) {
        $data.productQueryResult | ConvertFrom-Json
    } else {
        $data.productQueryResult
    }
    $body = $data.descComponentData.bodyLayout | ConvertTo-Json -Depth 100 -Compress
    $bodyBytes = [Text.Encoding]::UTF8.GetBytes($body)
    $bodySha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bodyBytes)).ToLowerInvariant()
    # Alibaba's compiled bodyLayout often emits protocol-relative image-bank URLs
    # (//sc04.alicdn.com/...) even when the editor was given an https URL. Count
    # both forms so a valid structured detail gallery is not reported as empty.
    $bodyImageMatches = [regex]::Matches($body, '(?i)(?:https?:)?//sc04\.alicdn\.com/kf/[^"\\ ]+')
    $bodyImageUrls = @($bodyImageMatches | ForEach-Object Value)
    $publicBodyAvailable = $null -ne $data.descComponentData.pageId -and $body.Length -gt 1000

    [pscustomobject]@{
        sku = $step.name.ToUpperInvariant()
        success = $true
        productId = $query.productId
        status = $query.status
        auditStatus = $query.auditStatus
        pageId = $data.descComponentData.pageId
        bodyLength = $body.Length
        bodySha256 = $bodySha256
        bodyImageUrls = $bodyImageUrls.Count
        uniqueBodyImageUrls = @($bodyImageUrls | Sort-Object -Unique).Count
        publicBodyAvailable = $publicBodyAvailable
        flyknit = ([regex]::Matches($body, '(?i)flyknit')).Count
        refundDeduct = ([regex]::Matches($body, '(?i)refund|deduct')).Count
        unsupportedWideToe = ([regex]::Matches($body, $wideRiskPattern)).Count
        accioUrl = ([regex]::Matches($body, '(?i)accio')).Count
        nestedAlibabaUrl = ([regex]::Matches($body, '(?i)sc04\.alicdn\.com/kf/[^/]+\.(?:png|jpe?g|webp)/286385890/')).Count
        productGalleryMarkers = ([regex]::Matches($body, '(?i)product-gallery')).Count
        companyGalleryMarkers = ([regex]::Matches($body, '(?i)company-gallery')).Count
        error = $null
    }
}

$summary = [pscustomobject]@{
    generatedAt = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
    total = @($rows).Count
    succeeded = @($rows | Where-Object success).Count
    failed = @($rows | Where-Object { -not $_.success }).Count
    online = @($rows | Where-Object { $_.status -eq 1 }).Count
    auditPassed = @($rows | Where-Object { $_.auditStatus -eq 1 }).Count
    publicBodyAvailable = @($rows | Where-Object { $_.publicBodyAvailable }).Count
    publicRiskClean = @($rows | Where-Object {
        $_.success -and $_.auditStatus -eq 1 -and $_.publicBodyAvailable -and
        $_.flyknit -eq 0 -and $_.refundDeduct -eq 0 -and
        $_.unsupportedWideToe -eq 0 -and $_.accioUrl -eq 0 -and $_.nestedAlibabaUrl -eq 0
    }).Count
}

$result = [pscustomobject]@{
    summary = $summary
    products = @($rows)
}
$result | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $reportPath -Encoding utf8
$result | ConvertTo-Json -Depth 20
