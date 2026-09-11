param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('T2VA', 'I2VA', 'FL2VA', 'L2VA', 'Ref2VA')]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$PromptPath,

    [Parameter(Mandatory = $true)]
    [ValidateRange(5, 362)]
    [int]$Frames
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$requiredFiles = @(
    'C:\Users\spq\.codex\skills\h3-prompt-writing\SKILL.md',
    (Join-Path $root 'MiniMax-H3本地生成规范.md'),
    (Join-Path $root '官方工作流\video_minimax_h3_t2v.json'),
    (Join-Path $root '官方工作流\video_minimax_h3_i2v.json'),
    (Join-Path $root '官方工作流\video_minimax_h3_r2v.json')
)

foreach ($requiredFile in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "缺少 H3 权威文件：$requiredFile"
    }
}

foreach ($workflow in $requiredFiles | Where-Object { $_ -like '*.json' }) {
    $null = Get-Content -Raw -LiteralPath $workflow | ConvertFrom-Json
}

$resolvedPrompt = (Resolve-Path -LiteralPath $PromptPath).Path
$content = Get-Content -Raw -LiteralPath $resolvedPrompt
$firstLine = (Get-Content -LiteralPath $resolvedPrompt -TotalCount 1).Trim()
$effectiveDuration = $Frames / 24
$durationText = $effectiveDuration.ToString('0.00', [Globalization.CultureInfo]::InvariantCulture)

if ($Frames % 17 -ne 5) {
    throw "非法 H3 帧数：$Frames。帧数必须满足 17k + 5。"
}

function Assert-OrderedFields {
    param([string[]]$Fields)

    $previousIndex = -1
    foreach ($field in $Fields) {
        $index = $content.IndexOf("${field}:", [StringComparison]::Ordinal)
        if ($index -lt 0) {
            throw "Prompt 缺少字段：$field"
        }
        if ($index -le $previousIndex) {
            throw "Prompt 字段顺序错误：$field"
        }
        $previousIndex = $index
    }
}

if ($Mode -eq 'Ref2VA') {
    Assert-OrderedFields @(
        'subject_definitions',
        'summary',
        'retention_analysis',
        'detailed_description',
        'overall_soundscape',
        'non_diegetic_music'
    )
    if ($content -notmatch '<(Picture|Video|Audio|Subject) [1-9]>') {
        throw 'Ref2VA Prompt 没有有效的官方参考标签。'
    }
}
else {
    Assert-OrderedFields @(
        'integrated_multimodal_description',
        'overall_soundscape',
        'non_diegetic_music'
    )

    switch ($Mode) {
        'T2VA' {
            if ($firstLine -notlike 'integrated_multimodal_description:*') {
                throw 'T2VA 必须直接以 integrated_multimodal_description 开始。'
            }
        }
        'I2VA' {
            $expected = 'For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.'
            if ($firstLine -ne $expected) {
                throw 'I2VA 首行不符合官方固定格式。'
            }
        }
        'FL2VA' {
            if ($firstLine -notlike 'How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot *) aligns with the *-second mark of the target video.') {
                throw 'FL2VA 首行不符合官方固定格式。'
            }
            if ($firstLine -notmatch [Regex]::Escape("$durationText-second mark")) {
                throw "FL2VA 尾帧时间必须使用实际时长 $durationText 秒。"
            }
        }
        'L2VA' {
            $l2vaPattern = '^How the reference pictures align with the target video — <Picture 1> \(from \[Shot [1-9][0-9]*\]\) aligns with the [0-9]+\.[0-9]{2}-second mark of the target video\.$'
            if ($firstLine -notmatch $l2vaPattern) {
                throw 'L2VA 首行不符合官方固定格式。'
            }
            if ($firstLine -notmatch [Regex]::Escape("$durationText-second mark")) {
                throw "L2VA 尾帧时间必须使用实际时长 $durationText 秒。"
            }
        }
    }
}

$forbiddenPatterns = @(
    'Strict negatives:',
    'lora_strength.*0\.(65|7|75|8)',
    'param_36=handle_file',
    'submit_minimax_from_slots'
)

foreach ($pattern in $forbiddenPatterns) {
    if ($content -match $pattern) {
        throw "Prompt 含已废弃模式：$pattern"
    }
}

[pscustomobject]@{
    Status = 'PASS'
    Mode = $Mode
    Prompt = $resolvedPrompt
    Frames = $Frames
    EffectiveDurationSeconds = $durationText
}
