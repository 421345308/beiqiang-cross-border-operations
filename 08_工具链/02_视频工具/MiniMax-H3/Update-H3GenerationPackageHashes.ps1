param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,

    [Parameter(Mandatory = $true)]
    [string]$ManifestPath
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

$promptPath = Resolve-ProjectFile $manifest.prompt_path
$canonicalCanvas = Resolve-ProjectFile $manifest.canonical_canvas_path
$reviewCanvas = Resolve-ProjectFile $manifest.review_canvas_path
foreach ($file in @($promptPath, $canonicalCanvas, $reviewCanvas)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "缺少生成包文件：$file" }
}

$null = Get-Content -Raw -Encoding UTF8 -LiteralPath $canonicalCanvas | ConvertFrom-Json
$null = Get-Content -Raw -Encoding UTF8 -LiteralPath $reviewCanvas | ConvertFrom-Json
& (Join-Path $toolRoot 'validate_h3_prompt.ps1') -Mode $manifest.mode -PromptPath $promptPath -Frames ([int]$manifest.parameters.frames) | Out-Null

$manifest.prompt_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $promptPath).Hash
$manifest.canonical_canvas_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $canonicalCanvas).Hash
$manifest.review_canvas_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $reviewCanvas).Hash

$resolvedApi = Resolve-ProjectFile $manifest.resolved_api_workflow_path
if (Test-Path -LiteralPath $resolvedApi -PathType Leaf) {
    $null = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedApi | ConvertFrom-Json
    $manifest.resolved_api_workflow_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedApi).Hash
} else {
    $manifest.resolved_api_workflow_sha256 = ''
    if ($manifest.status -ne 'draft') { $manifest.status = 'draft' }
}

$utf8NoBom = [Text.UTF8Encoding]::new($false)
$json = $manifest | ConvertTo-Json -Depth 10
[IO.File]::WriteAllText($resolvedManifest, ($json + [Environment]::NewLine), $utf8NoBom)

[pscustomobject]@{
    Status = 'UPDATED'
    CandidateId = $manifest.candidate_id
    PromptSha256 = $manifest.prompt_sha256
    ReviewCanvasSha256 = $manifest.review_canvas_sha256
    ApiWorkflowPresent = (Test-Path -LiteralPath $resolvedApi -PathType Leaf)
    PackageState = $manifest.status
}
