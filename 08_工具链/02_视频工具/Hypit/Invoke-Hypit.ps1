[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$HypitArgs
)

$ErrorActionPreference = 'Stop'

$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$distributionRoot = Join-Path $toolRoot 'distribution'
$hypitCli = Join-Path $distributionRoot 'node_modules\@hypit\hypit\bin\hypit.mjs'
$distributionInitializer = Join-Path $toolRoot 'Initialize-HypitDistribution.ps1'
$ffmpegBin = Join-Path (Split-Path -Parent $toolRoot) 'ffmpeg\ffmpeg-9.0-essentials_build\bin'

if (-not (Test-Path -LiteralPath $hypitCli)) {
    throw "Hypit Distribution is not installed. Run npm install in: $distributionRoot"
}

& $distributionInitializer

$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$nodePath = if ($nodeCommand) { $nodeCommand.Source } else { $null }
$nodeVersion = if ($nodePath) { (& $nodePath --version).TrimStart('v') } else { $null }

if (-not $nodeVersion -or [version]$nodeVersion -lt [version]'22.15.0') {
    $bundledNode = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
    if (Test-Path -LiteralPath $bundledNode) {
        $nodePath = $bundledNode
        $nodeVersion = (& $nodePath --version).TrimStart('v')
    }
}

if (-not $nodePath -or [version]$nodeVersion -lt [version]'22.15.0') {
    throw 'Hypit requires Node.js 22.15.0 or newer.'
}

$nodeBin = Split-Path -Parent $nodePath
$env:PATH = "$nodeBin;$env:PATH"

if (Test-Path -LiteralPath $ffmpegBin) {
    $env:PATH = "$ffmpegBin;$env:PATH"
}

& $nodePath $hypitCli @HypitArgs
exit $LASTEXITCODE
