[CmdletBinding()]
param([Parameter(Mandatory)][string]$Prepared, [Parameter(Mandatory)][string]$EvidenceDirectory)
$ErrorActionPreference = 'Stop'
$preparedPath = (Resolve-Path -LiteralPath $Prepared).Path
$job = Get-Content -LiteralPath $preparedPath -Raw -Encoding utf8 | ConvertFrom-Json
if ($job.schema -ne 'reference-remake-prepared-v1') { throw 'Unsupported prepared package.' }
if (-not $job.libtv -or -not $job.libtv.project_uuid -or -not $job.libtv.draft_node_id -or -not $job.libtv.reference_video_node_id) {
    throw 'Local research package has no actual platform bindings. No upload or CLI action performed.'
}
function Assert-Hash($Path, $Expected) {
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Expected) {
        throw "Input changed: $Path. Prepare and review again."
    }
}
Assert-Hash $job.package_path $job.package_sha256
Assert-Hash $job.prompt_path $job.prompt_sha256
Assert-Hash $job.reference_video.path $job.reference_video.sha256
foreach ($image in $job.reference_images) { Assert-Hash $image.path $image.sha256 }
New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
$evidence = (Resolve-Path -LiteralPath $EvidenceDirectory).Path
function Invoke-LibTVJson([string[]]$CliArgs, [string]$Receipt) {
    # Native argument arrays: never concatenate commands or use Invoke-Expression.
    $text = & libtv @CliArgs
    if ($LASTEXITCODE -ne 0) { throw 'LibTV operation failed. Inspect state before repeating; no automatic retry.' }
    $joined = $text -join "`n"
    $value = $joined | ConvertFrom-Json
    $joined | Set-Content -LiteralPath (Join-Path $evidence $Receipt) -Encoding utf8
    return $value
}
$project = $job.libtv.project_uuid
$draft = $job.libtv.draft_node_id
$before = Invoke-LibTVJson @('node', $draft, '-p', $project) 'draft-before.json'
if ($before.data.url.Count -gt 0) { throw 'Draft already has output. Do not overwrite a completed result.' }
$video = Invoke-LibTVJson @('node', $job.libtv.reference_video_node_id, '-p', $project) 'reference-video.json'
if ($video.nodeType -ne 'video' -or $video.data.url.Count -eq 0) { throw 'Reference video node has no uploaded video.' }
$imageIds = @()
for ($i = 0; $i -lt $job.reference_images.Count; $i++) {
    $image = $job.reference_images[$i]
    $receipt = 'product-upload-' + $image.sha256 + '.json'
    $receiptPath = Join-Path $evidence $receipt
    if (Test-Path -LiteralPath $receiptPath) {
        $saved = Get-Content -LiteralPath $receiptPath -Raw -Encoding utf8 | ConvertFrom-Json
        $uploaded = Invoke-LibTVJson @('node', $saved.nodeKey, '-p', $project) ('product-readback-' + $i + '.json')
        if ($uploaded.nodeType -ne 'image' -or $uploaded.data.url.Count -eq 0) { throw 'Uploaded image is no longer available.' }
    } else {
        $name = $job.product_id + '｜真实商品参考' + ($i + 1) + '｜' + $image.sha256.Substring(0, 8)
        $uploaded = Invoke-LibTVJson @('upload', $name, '-p', $project, '-t', 'image', '-f', $image.path) $receipt
    }
    if (-not $uploaded.nodeKey) { throw 'Upload has no node receipt; stop and inspect instead of reuploading.' }
    $imageIds += $uploaded.nodeKey
}
$prompt = Get-Content -LiteralPath $job.prompt_path -Raw -Encoding utf8
$prompt = $prompt.Replace('@视频1', '{{Node ' + $video.nodeKey + '}}')
for ($i = 0; $i -lt $imageIds.Count; $i++) {
    $prompt = $prompt.Replace($job.reference_images[$i].binding, '{{Node ' + $imageIds[$i] + '}}')
}
$prompt | Set-Content -LiteralPath (Join-Path $evidence 'bound-prompt.txt') -Encoding utf8
$expected = @($video.nodeKey) + $imageIds
$cli = @('node', $draft, '-p', $project, '--prompt', $prompt)
foreach ($old in @($before.data.params.mixedList)) {
    if ($old.nodeId -notin $expected) { $cli += @('--left-rm', $old.nodeId) }
}
foreach ($id in $expected) { $cli += @('--left-add', $id) }
$s = $job.settings
$cli += @('-s', 'model=Seedance 2.5', '-s', 'modeType=mixed2video', '-s', 'count=1',
          '-s', ('duration=' + $s.duration), '-s', ('ratio=' + $s.ratio),
          '-s', ('resolution=' + $s.resolution), '-s', ('enableSound=' + $s.enableSound), '-s', 'searchEnabled=0')
# Intentionally no generation switch. This tool only stages uploaded references and draft settings.
$null = Invoke-LibTVJson $cli 'draft-update.json'
$after = Invoke-LibTVJson @('node', $draft, '-p', $project) 'draft-readback.json'
$p = $after.data.params
# CLI 1.1.3 recomputes lists for execution and forbids manually setting mixedList.
# Check current per-type bindings/order and expose a stale cached mixedList separately.
$actual = @($p.videoList | ForEach-Object nodeId) + @($p.imageList | ForEach-Object nodeId)
if ((($actual | Sort-Object) -join ',') -ne (($expected | Sort-Object) -join ',')) { throw 'Reference bindings mismatch.' }
if ($p.mixedListOrder.Count -ne $expected.Count -or (@($p.mixedListOrder | Sort-Object -Unique).Count -ne $expected.Count) -or
    ((@($p.mixedListOrder | Sort-Object) -join ',') -ne (($expected | Sort-Object) -join ','))) { throw 'Reference order coverage mismatch.' }
$cachedIds = @($p.mixedList | ForEach-Object nodeId)
$cachePresent = $null -ne $p.PSObject.Properties['mixedList']
$cacheMatches = $cachePresent -and (($cachedIds -join ',') -eq (@($p.mixedListOrder) -join ','))
$cacheState = if (-not $cachePresent) { 'absent_derived_from_typed_inputs' } elseif ($cacheMatches) { 'matches_current_inputs' } else { 'stale' }
foreach ($key in @('duration', 'ratio', 'resolution', 'enableSound')) {
    if ($p.settings.$key -ne $s.$key) { throw "Setting mismatch: $key" }
}
if ($p.prompt.Replace("`r`n", "`n").TrimEnd() -ne $prompt.Replace("`r`n", "`n").TrimEnd() -or $p.count -ne 1 -or $p.modeType -ne 'mixed2video') { throw 'Prompt or generation contract mismatch.' }
if ($p.advancedSettings.search_enabled -ne 0) { throw 'Web search must be disabled.' }
if ($after.data.url.Count -gt 0) { throw 'Unexpected generated output.' }
[ordered]@{ state='draft_bound_not_generated'; project_uuid=$project; draft_node_id=$draft;
    product_image_node_ids=$imageIds; reference_video_node_id=$video.nodeKey;
    prepared_sha256=(Get-FileHash -LiteralPath $preparedPath).Hash.ToLowerInvariant();
    generation_submitted=$false; quote_status='requires_current_page_read';
    mixed_input_node_ids=@($p.mixedListOrder); mixed_list_cache_state=$cacheState;
    cached_mixed_list_matches=$cacheMatches; generation_ready=$false;
    remaining=@('logged_in_page_final_quote_and_visible_reference_confirmation', 'paid_generation_scope');
    whole_output_seconds=$s.duration } | ConvertTo-Json -Depth 10 |
    Set-Content -LiteralPath (Join-Path $evidence 'stage-state.json') -Encoding utf8
Write-Output ('Draft lists/order/prompt/settings verified. Cached mixed list matches: ' + $cacheMatches + '. Generation not submitted; final page verification still required.')
