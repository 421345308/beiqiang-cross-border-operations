param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,

    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [switch]$RequireReady
)

$ErrorActionPreference = 'Stop'
$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectPath = [IO.Path]::GetFullPath($ProjectRoot)
$resolvedManifest = (Resolve-Path -LiteralPath $ManifestPath).Path
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedManifest | ConvertFrom-Json

function Resolve-ProjectFile([string]$value) {
    if ([IO.Path]::IsPathRooted($value)) { return [IO.Path]::GetFullPath($value) }
    return [IO.Path]::GetFullPath((Join-Path $projectPath $value))
}

$requiredText = @('candidate_id', 'shot_id', 'prompt_path', 'canonical_canvas_path', 'review_canvas_path', 'mode', 'expected_output', 'status')
foreach ($field in $requiredText) {
    if ([string]::IsNullOrWhiteSpace([string]$manifest.$field)) { throw "Manifest 缺少字段：$field" }
}

$promptPath = Resolve-ProjectFile $manifest.prompt_path
$canonicalCanvas = Resolve-ProjectFile $manifest.canonical_canvas_path
$reviewCanvas = Resolve-ProjectFile $manifest.review_canvas_path
foreach ($file in @($promptPath, $canonicalCanvas, $reviewCanvas)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "缺少生成包文件：$file" }
    $null = Get-Content -Raw -Encoding UTF8 -LiteralPath $file
}
$null = Get-Content -Raw -Encoding UTF8 -LiteralPath $canonicalCanvas | ConvertFrom-Json
$null = Get-Content -Raw -Encoding UTF8 -LiteralPath $reviewCanvas | ConvertFrom-Json

$promptHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $promptPath).Hash
$canonicalHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $canonicalCanvas).Hash
$reviewHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $reviewCanvas).Hash
if ($promptHash -ne $manifest.prompt_sha256) { throw 'Prompt 已修改但 Manifest 哈希未更新。' }
if ($canonicalHash -ne $manifest.canonical_canvas_sha256) { throw '中央画布版本已变化，请建立新候选或重新确认。' }
if ($reviewHash -ne $manifest.review_canvas_sha256) { throw '审阅画布已修改但 Manifest 哈希未更新。' }

$frames = [int]$manifest.parameters.frames
& (Join-Path $toolRoot 'validate_h3_prompt.ps1') -Mode $manifest.mode -PromptPath $promptPath -Frames $frames | Out-Null

if ($RequireReady) {
    if ($manifest.status -ne 'ready') { throw "候选状态不是 ready：$($manifest.status)" }
    if ($manifest.references.Count -eq 0 -and $manifest.mode -ne 'T2VA') { throw '非 T2VA 候选尚未登记参考素材。' }
    $resolvedApi = Resolve-ProjectFile $manifest.resolved_api_workflow_path
    if (-not (Test-Path -LiteralPath $resolvedApi -PathType Leaf)) { throw "缺少实际提交 API 图：$resolvedApi" }
    $null = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedApi | ConvertFrom-Json
    $apiHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedApi).Hash
    if ($apiHash -ne $manifest.resolved_api_workflow_sha256) { throw '实际 API 图哈希与 Manifest 不一致。' }
}

[pscustomobject]@{
    Status = 'PASS'
    CandidateId = $manifest.candidate_id
    Mode = $manifest.mode
    PackageState = $manifest.status
    Prompt = $promptPath
    ReviewCanvas = $reviewCanvas
    RequireReady = [bool]$RequireReady
}
