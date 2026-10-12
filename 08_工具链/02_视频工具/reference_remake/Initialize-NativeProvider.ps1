[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Prepared,
    [Parameter(Mandatory)][string]$Workspace,
    [Parameter(Mandatory)][string]$EvidenceDirectory,
    [Parameter(Mandatory)][string]$FFprobe
)
$ErrorActionPreference = 'Stop'
$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$provider = Join-Path $toolRoot 'provider-libtv'
$preparedPath = (Resolve-Path -LiteralPath $Prepared).Path
$job = Get-Content -LiteralPath $preparedPath -Raw -Encoding utf8 | ConvertFrom-Json
if ($job.schema -ne 'reference-remake-prepared-v1') { throw 'Unsupported prepared package.' }
New-Item -ItemType Directory -Force -Path $Workspace | Out-Null
$nativeRoot = (Resolve-Path -LiteralPath $Workspace).Path
$evidencePath = [IO.Path]::GetFullPath($EvidenceDirectory)
$probePath = (Resolve-Path -LiteralPath $FFprobe).Path
$cliPath = (Get-Command libtv -ErrorAction Stop).Source
if ([IO.Path]::GetExtension($cliPath) -in @('.cmd', '.bat', '.ps1')) {
    throw 'Use a native LibTV executable, not a shell shim, for safe argv transport.'
}
$scope = Join-Path $nativeRoot 'node_modules/@beiqiang'
New-Item -ItemType Directory -Force -Path $scope | Out-Null
$link = Join-Path $scope 'provider-libtv'
if (Test-Path -LiteralPath $link) {
    if ((Get-Item -LiteralPath $link).Target -ne (Resolve-Path -LiteralPath $provider).Path) {
        throw 'Existing provider dependency points elsewhere; do not overwrite it.'
    }
} else { New-Item -ItemType Junction -Path $link -Target $provider | Out-Null }
@{ name='reference-remake-native'; version='0.0.0'; private=$true; type='module';
    dependencies=@{ '@beiqiang/provider-libtv'='file:' + $provider.Replace('\','/') } } |
    ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $nativeRoot 'package.json') -Encoding utf8
$nativeProfile = @{ format='hypit.runtime-local@1'; dataRoot='.hypit/execution';
    endpoints=@{ 'libtv.reference'=@{ use='@beiqiang/provider-libtv'; config=@{
        prepared=$preparedPath; evidenceDirectory=$evidencePath; executable=$cliPath; ffprobe=$probePath
    } } }; bindings=@{ '@hypit/seedance@1#seedance-2.5'='libtv.reference' } }
# Authorization is deliberately absent. Installing/checking/planning never authorizes generation.
$nativeProfile | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $nativeRoot 'hypit.runtime.json') -Encoding utf8
function Escape-Xml([string]$Text) { return [Security.SecurityElement]::Escape($Text) }
function Link-Asset([string]$Name, [string]$Path) {
    $assetRoot = Join-Path $nativeRoot 'assets'
    New-Item -ItemType Directory -Force -Path $assetRoot | Out-Null
    $target = (Resolve-Path -LiteralPath (Split-Path -Parent $Path)).Path
    $assetLink = Join-Path $assetRoot $Name
    if (Test-Path -LiteralPath $assetLink) {
        if ((Get-Item -LiteralPath $assetLink).Target -ne $target) { throw 'Existing asset link points elsewhere.' }
    } else { New-Item -ItemType Junction -Path $assetLink -Target $target | Out-Null }
    # Hypit requires relative source locators. Links reuse originals without duplicating media.
    return './assets/' + $Name + '/' + (Split-Path -Leaf $Path)
}
$prompt = Escape-Xml (Get-Content -LiteralPath $job.prompt_path -Raw -Encoding utf8)
$videoPath = Escape-Xml (Link-Asset 'reference' $job.reference_video.path)
$lines = @('<?svml using="@hypit/markup@1"?>', '<svml>',
    '  <import as="text" from="@hypit/text@1"/>', '  <import as="media" from="@hypit/media@1"/>',
    '  <import as="seedance" from="@hypit/seedance@1"/>',
    ('  <text:Value id="direction">' + $prompt + '</text:Value>'),
    ('  <media:Video id="reference" src="' + $videoPath + '"/>'))
for ($i=0; $i -lt $job.reference_images.Count; $i++) {
    $imagePath = Escape-Xml (Link-Asset ('product' + ($i + 1)) $job.reference_images[$i].path)
    $lines += '  <media:Image id="product' + ($i + 1) + '" src="' + $imagePath + '"/>'
}
$s = $job.settings
$sound = if ($s.enableSound -eq 'on') { 'true' } else { 'false' }
$lines += '  <seedance:ReferenceVideo id="whole" model="2.5" prompt={direction} duration="' + $s.duration +
    '" resolution="' + $s.resolution + '" aspect-ratio="' + $s.ratio + '" generate-audio="' + $sound + '">'
$lines += '    <seedance:Reference video={reference}/>'
for ($i=0; $i -lt $job.reference_images.Count; $i++) { $lines += '    <seedance:Reference image={product' + ($i + 1) + '}/>' }
$lines += @('  </seedance:ReferenceVideo>', '</svml>')
$lines | Set-Content -LiteralPath (Join-Path $nativeRoot 'whole.svml') -Encoding utf8
@('<?svml using="@hypit/run-markup@1"?>', '<svrun version="1">',
    '  <author source="./whole.svml"/>', '  <target output="whole.video"/>', '</svrun>') |
    Set-Content -LiteralPath (Join-Path $nativeRoot 'whole.svrun') -Encoding utf8
Write-Output 'Native Provider installed for this workspace. Source/Run/Profile ready; paid generation disabled.'
