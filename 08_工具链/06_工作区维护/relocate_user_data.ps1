param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('conda-envs','conda-pkgs','desktop-110808','desktop-theshy','android-avd','jetbrains','whisper','downloads','huggingface','modelscope')]
    [string[]]$Targets,
    [switch]$AllowAppDataDesktop
)
$ErrorActionPreference = 'Stop'
$plans = @{
    'conda-envs' = @('C:\Users\spq\.conda\envs', 'E:\C盘迁移\Python\envs', 'python|conda')
    'conda-pkgs' = @('C:\Users\spq\.conda\pkgs', 'E:\C盘迁移\Python\pkgs', 'conda')
    'desktop-110808' = @('C:\Users\spq\Desktop\110808', 'E:\C盘迁移\桌面\110808', '')
    'desktop-theshy' = @('C:\Users\spq\Desktop\TheShy白衣神王剪辑项目', 'E:\C盘迁移\桌面\TheShy白衣神王剪辑项目', 'ffmpeg|Jianying|DaVinci|Adobe')
    'android-avd' = @('C:\Users\spq\.android\avd', 'E:\C盘迁移\Android\avd', 'emulator|qemu|studio64')
    'jetbrains' = @('C:\Users\spq\AppData\Local\JetBrains', 'E:\C盘迁移\JetBrains', 'idea64|pycharm64|studio64')
    'whisper' = @('C:\Users\spq\.cache\whisper', 'E:\C盘迁移\模型\whisper', '')
    'downloads' = @('C:\Users\spq\Downloads', 'E:\C盘迁移\下载', '')
    'huggingface' = @('C:\Users\spq\.cache\huggingface', 'E:\C盘迁移\模型\huggingface', '')
    'modelscope' = @('C:\Users\spq\.cache\modelscope', 'E:\C盘迁移\模型\modelscope', '')
}
$python = 'C:\ProgramData\anaconda3\python.exe'
$verifier = Join-Path $PSScriptRoot 'verify_disk_migration.py'
$evidence = 'E:\C盘迁移\迁移校验'
if ((Get-Volume -DriveLetter E).FileSystem -ne 'NTFS') { throw 'E must be NTFS' }
if ((Get-Volume -DriveLetter E).DriveType -ne 'Fixed') { throw 'E must be a fixed drive' }
New-Item -ItemType Directory -Path $evidence -Force | Out-Null
foreach ($target in $Targets) {
    $source,$destination,$processPattern = $plans[$target]
    $source = [IO.Path]::GetFullPath($source).TrimEnd('\')
    $destination = [IO.Path]::GetFullPath($destination).TrimEnd('\')
    if (-not $source.StartsWith('C:\Users\spq\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid source boundary' }
    if (-not $destination.StartsWith('E:\C盘迁移\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid destination boundary' }
    if ($source.StartsWith('C:\Users\spq\AppData\',[StringComparison]::OrdinalIgnoreCase)) {
        if (-not $AllowAppDataDesktop) { throw 'AppData relocation requires an ordinary Windows desktop launch with -AllowAppDataDesktop; do not run it inside Codex' }
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class RelocationPackageIdentity {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode)]
    public static extern int GetCurrentPackageFullName(ref UInt32 length, IntPtr packageName);
}
'@
        [uint32]$packageNameLength=0
        if ([RelocationPackageIdentity]::GetCurrentPackageFullName([ref]$packageNameLength,[IntPtr]::Zero) -ne 15700) {
            throw 'AppData migration must run outside packaged application file virtualization'
        }
    }
    $item = Get-Item -LiteralPath $source -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        if ($item.LinkType -eq 'Junction' -and $item.Target -eq $destination) {
            Write-Output "$target is already relocated"
            continue
        }
        throw 'Source is an unexpected link'
    }
    if (Test-Path -LiteralPath $destination) { throw "Destination already exists: $destination" }
    # Check every ancestor before any cross-volume move; never follow a redirected root.
    foreach ($path in @($source, (Split-Path $destination -Parent))) {
        $ancestor = $path
        while ($ancestor -and $ancestor.Length -gt 3) {
            if (Test-Path -LiteralPath $ancestor) {
                if ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Linked ancestor: $ancestor" }
            }
            $ancestor = Split-Path $ancestor -Parent
        }
    }
    $processes = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -notmatch '^(pwsh|powershell)\.exe$' })
    $related = @($processes | Where-Object {
        ($_.ExecutablePath -and $_.ExecutablePath.StartsWith($source+'\',[StringComparison]::OrdinalIgnoreCase)) -or
        ($_.CommandLine -and $_.CommandLine.IndexOf($source,[StringComparison]::OrdinalIgnoreCase) -ge 0)
    })
    # Base Python is outside .conda and remains available for the verification helper.
    if ($processPattern -and $target -notin @('conda-envs','conda-pkgs')) {
        $related += @($processes | Where-Object { $_.Name -match $processPattern })
    }
    if ($target -in @('conda-envs','conda-pkgs')) {
        $related += @($processes | Where-Object { $_.Name -match '^conda' })
    }
    if ($related.Count -gt 0) { throw "Related process is running: $($related.Name -join ', ')" }
    $manifest = Join-Path $evidence "$target-manifest.json"
    Write-Output "START $target; checking original content"
    & $python $verifier manifest $source $manifest
    if ($LASTEXITCODE -ne 0) { throw 'Source manifest failed' }
    $manifestData = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
    $totalBytes = [long]0
    foreach ($property in $manifestData.files.PSObject.Properties) { $totalBytes += [long]$property.Value[0] }
    if ((Get-PSDrive E).Free -lt $totalBytes + 2GB) { throw 'Insufficient E drive space' }
    New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
    Write-Output "MOVE $target"
    # Native relocation, restricted to the two absolute, checked directories above.
    $copyLog = Join-Path $evidence "$target-robocopy.log"
    & robocopy.exe $source $destination /E /MOVE /COPY:DAT /DCOPY:DAT /XJ /R:1 /W:1 /MT:8 /NP /NFL /NDL "/LOG:$copyLog"
    if ($LASTEXITCODE -ge 8) { throw 'Move incomplete; originals remain split between source and destination. Do not delete either.' }
    & $python $verifier verify $destination $manifest
    if ($LASTEXITCODE -ne 0) { throw 'Content verification failed; destination must be preserved' }
    if (Test-Path -LiteralPath $source) { throw 'Source still exists; do not replace it automatically' }
    New-Item -ItemType Junction -Path $source -Target $destination | Out-Null
    $link = Get-Item -LiteralPath $source -Force
    if ($link.LinkType -ne 'Junction' -or $link.Target -ne $destination) { throw 'Junction validation failed' }
    $record = [ordered]@{target=$target;source=$source;destination=$destination;bytes=$totalBytes;verified=$true;date=(Get-Date -Format o);freeC=(Get-PSDrive C).Free}
    $record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $evidence "$target-result.json") -Encoding utf8
    Write-Output ($record | ConvertTo-Json -Compress)
}
