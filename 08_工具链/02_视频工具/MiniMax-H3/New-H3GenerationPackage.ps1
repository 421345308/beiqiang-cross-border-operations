param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9_-]+$')]
    [string]$ShotId,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9_-]+$')]
    [string]$CandidateId,

    [Parameter(Mandatory = $true)]
    [ValidateSet('T2VA', 'I2VA', 'FL2VA', 'L2VA', 'Ref2VA')]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [int]$Width,

    [Parameter(Mandatory = $true)]
    [int]$Height,

    [Parameter(Mandatory = $true)]
    [ValidateRange(5, 362)]
    [int]$Frames,

    [Parameter(Mandatory = $true)]
    [long]$Seed,

    [string]$ChangedVariable = 'initial candidate',
    [string[]]$FrozenProperty = @()
)

$ErrorActionPreference = 'Stop'
$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectPath = [IO.Path]::GetFullPath($ProjectRoot)

if ($Width % 32 -ne 0 -or $Height % 32 -ne 0) {
    throw "宽高必须是 32 的倍数：${Width}x${Height}"
}
if ($Frames % 17 -ne 5) {
    throw "非法 H3 帧数：$Frames。帧数必须满足 17k + 5。"
}

$duration = $Frames / 24
$durationText = $duration.ToString('0.00', [Globalization.CultureInfo]::InvariantCulture)
$packageRoot = Join-Path $projectPath 'generation'
$promptDir = Join-Path $packageRoot 'prompts'
$manifestDir = Join-Path $packageRoot 'manifests'
$reviewCanvasDir = Join-Path $packageRoot 'workflows\review'
$resolvedDir = Join-Path $packageRoot 'workflows\resolved'
$outputDir = Join-Path $packageRoot 'outputs\candidates'

$promptPath = Join-Path $promptDir "$CandidateId.txt"
$manifestPath = Join-Path $manifestDir "$CandidateId.json"
$reviewCanvasPath = Join-Path $reviewCanvasDir "$CandidateId.canvas.json"
$resolvedApiPath = Join-Path $resolvedDir "$CandidateId.api.json"
$expectedOutput = Join-Path $outputDir "$CandidateId.mp4"

$targets = @($promptPath, $manifestPath, $reviewCanvasPath)
foreach ($target in $targets) {
    if (Test-Path -LiteralPath $target) {
        throw "候选文件已存在，未覆盖：$target。请使用新的 CandidateId。"
    }
}

foreach ($dir in @($promptDir, $manifestDir, $reviewCanvasDir, $resolvedDir, $outputDir)) {
    $null = New-Item -ItemType Directory -Force -Path $dir
}

switch ($Mode) {
    'T2VA' {
        $canonicalCanvas = Join-Path $toolRoot '官方工作流\video_minimax_h3_t2v.json'
        $prompt = @"
integrated_multimodal_description: [Shot 1] TODO: describe the visible composition, subject, environment, one continuous action, camera movement, and synchronized diegetic sound for this shot.

overall_soundscape: N/A

non_diegetic_music: N/A
"@
    }
    'I2VA' {
        $canonicalCanvas = Join-Path $toolRoot '官方工作流\video_minimax_h3_i2v.json'
        $prompt = @"
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description: [Shot 1] TODO: begin exactly from <Picture 1>, preserve its visible identity, clothing, environment, composition, and lighting, then describe one continuous action and camera path.

overall_soundscape: N/A

non_diegetic_music: N/A
"@
    }
    'FL2VA' {
        $canonicalCanvas = Join-Path $toolRoot '官方工作流\video_minimax_h3_i2v.json'
        $prompt = @"
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the $durationText-second mark of the target video.

integrated_multimodal_description: [Shot 1] TODO: begin from Picture 1 and describe the visible, continuous motion path that progressively reaches Picture 2 at the final frame.

overall_soundscape: N/A

non_diegetic_music: N/A
"@
    }
    'L2VA' {
        $canonicalCanvas = Join-Path $toolRoot '官方工作流\video_minimax_h3_i2v.json'
        $prompt = @"
How the reference pictures align with the target video — <Picture 1> (from [Shot 1]) aligns with the $durationText-second mark of the target video.

integrated_multimodal_description: [Shot 1] TODO: infer a plausible earlier state and describe the continuous action, camera, and composition path that lands exactly on <Picture 1> at the final frame.

overall_soundscape: N/A

non_diegetic_music: N/A
"@
    }
    'Ref2VA' {
        $canonicalCanvas = Join-Path $toolRoot '官方工作流\video_minimax_h3_r2v.json'
        $prompt = @"
subject_definitions:
<Subject 1> is TODO, referenced from <Picture 1>; define exactly which identity, costume, scene, action, camera, or style attributes this reference provides.

summary:
[reference generation] The target video shows <Subject 1> performing one clear continuous event.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - TODO: state the visible attributes that must remain stable.

detailed_description:
The target video uses TODO visual language.
[Shot 1] TODO: describe composition, subject positions, environment, lighting, continuous action causality, camera motion, sound, and the exact point where each reference takes effect.

overall_soundscape:
N/A

non_diegetic_music:
N/A
"@
    }
}

$modelName = if ($Mode -eq 'Ref2VA') {
    'minimax_h3_ref2va_pruned_int8_convrot.safetensors'
} else {
    'minimax_h3_fl2va_pruned_int8_convrot.safetensors'
}
$loraName = if ($Mode -eq 'Ref2VA') {
    ''
} else {
    'minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors'
}
$loraStrength = if ($Mode -eq 'Ref2VA') { $null } else { 1.0 }
$stepCount = if ($Mode -eq 'Ref2VA') { 20 } else { 8 }

if (-not (Test-Path -LiteralPath $canonicalCanvas -PathType Leaf)) {
    throw "缺少中央官方画布：$canonicalCanvas"
}

$utf8NoBom = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText($promptPath, ($prompt.TrimEnd() + [Environment]::NewLine), $utf8NoBom)
Copy-Item -LiteralPath $canonicalCanvas -Destination $reviewCanvasPath -Force

$promptHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $promptPath).Hash
$canvasHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $canonicalCanvas).Hash
$reviewCanvasHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $reviewCanvasPath).Hash

$manifest = [ordered]@{
    schema_version = '1'
    candidate_id = $CandidateId
    shot_id = $ShotId
    created_at = [DateTimeOffset]::Now.ToString('o')
    prompt_path = [IO.Path]::GetRelativePath($projectPath, $promptPath).Replace('\', '/')
    prompt_sha256 = $promptHash
    canonical_canvas_path = $canonicalCanvas
    canonical_canvas_sha256 = $canvasHash
    review_canvas_path = [IO.Path]::GetRelativePath($projectPath, $reviewCanvasPath).Replace('\', '/')
    review_canvas_sha256 = $reviewCanvasHash
    resolved_api_workflow_path = [IO.Path]::GetRelativePath($projectPath, $resolvedApiPath).Replace('\', '/')
    resolved_api_workflow_sha256 = ''
    mode = $Mode
    references = @()
    parameters = [ordered]@{
        seed = $Seed
        width = $Width
        height = $Height
        frames = $Frames
        effective_duration_seconds = [Math]::Round($duration, 6)
        model = $modelName
        lora = $loraName
        lora_strength = $loraStrength
        steps = $stepCount
        sampler = 'res_multistep'
        scheduler = 'simple'
        reference_image_size = $(if ($Mode -eq 'Ref2VA') { 'match' } else { '' })
    }
    changed_variable = $ChangedVariable
    frozen_properties = @($FrozenProperty)
    acceptance_focus = @()
    expected_output = [IO.Path]::GetRelativePath($projectPath, $expectedOutput).Replace('\', '/')
    remote_job_id = ''
    status = 'draft'
}

$manifestJson = $manifest | ConvertTo-Json -Depth 10
[IO.File]::WriteAllText($manifestPath, ($manifestJson + [Environment]::NewLine), $utf8NoBom)

& (Join-Path $toolRoot 'validate_h3_prompt.ps1') -Mode $Mode -PromptPath $promptPath -Frames $Frames | Out-Null

[pscustomobject]@{
    Status = 'CREATED'
    CandidateId = $CandidateId
    Mode = $Mode
    Prompt = $promptPath
    ReviewCanvas = $reviewCanvasPath
    Manifest = $manifestPath
    EffectiveDurationSeconds = $durationText
    Note = '请编辑 Prompt 和 Manifest；实际 API 图生成并校验后再把 status 改为 ready。'
}
