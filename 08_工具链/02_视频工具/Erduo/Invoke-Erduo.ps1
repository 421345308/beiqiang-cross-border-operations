[CmdletBinding()]
param(
    [ValidateSet('runtime', 'plan', 'task', 'render')]
    [string]$Mode = 'runtime',
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ToolArgs
)
$ErrorActionPreference = 'Stop'
$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillRoot = Join-Path $toolRoot 'upstream/erduo-broll-loop-engineering'
$runtimeCli = Join-Path $toolRoot 'upstream/runtime/node_modules/hyperframes/bin/hyperframes.mjs'
$nodePath = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
if (-not (Test-Path -LiteralPath $nodePath)) { $nodePath = (Get-Command node -ErrorAction Stop).Source }
if ([version]((& $nodePath --version).TrimStart('v')) -lt [version]'22.20.0') { throw 'Erduo requires Node 22.20.0 or newer.' }
$scriptPath = switch ($Mode) {
    'runtime' { $runtimeCli }
    'plan' { Join-Path $skillRoot 'scripts/lean-plan.mjs' }
    'task' { Join-Path $skillRoot 'scripts/prepare-creative-task.mjs' }
    'render' { Join-Path $toolRoot 'render-windows.mjs' }
}
if (-not (Test-Path -LiteralPath $scriptPath)) { throw "Missing local command: $scriptPath" }
& $nodePath (Join-Path $toolRoot 'launch-windows.mjs') -- $nodePath $scriptPath @ToolArgs
exit $LASTEXITCODE
