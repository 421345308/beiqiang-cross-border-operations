param([switch]$InspectOnly)
$ErrorActionPreference = 'Stop'
$source = 'C:\Users\spq\.codex'
$destination = 'E:\C盘迁移\Codex\.codex'
$transaction = 'C:\Users\spq\.codex-migration-source'
$python = 'C:\ProgramData\anaconda3\python.exe'
$verifier = Join-Path $PSScriptRoot 'verify_disk_migration.py'
$evidence = 'E:\C盘迁移\迁移校验'

function Get-CodexUsers {
    @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -notmatch '^(pwsh|powershell)\.exe$' -and
        ($_.Name -match '^(ChatGPT|codex|codex-code-mode-host|codex-computer-use-swift)\.exe$' -or
         ($_.ExecutablePath -and ($_.ExecutablePath.StartsWith('C:\Users\spq\.codex\',[StringComparison]::OrdinalIgnoreCase) -or
          $_.ExecutablePath.IndexOf('\Local\OpenAI\Codex\',[StringComparison]::OrdinalIgnoreCase) -ge 0)) -or
         ($_.CommandLine -and $_.CommandLine.IndexOf('C:\Users\spq\.codex\',[StringComparison]::OrdinalIgnoreCase) -ge 0))
    })
}

function Assert-UnlinkedAncestors([string]$path) {
    $current = [IO.Path]::GetFullPath($path)
    while ($current -and $current.Length -gt 3) {
        if (Test-Path -LiteralPath $current) {
            if ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Unexpected linked path: $current"
            }
        }
        $current = Split-Path $current -Parent
    }
}

function Remove-VerifiedOriginal {
    # Delete only the old, verified transaction directory. Never recurse into any link target.
    $root = [IO.Path]::GetFullPath($transaction).TrimEnd('\')
    if ($root -ne 'C:\Users\spq\.codex-migration-source') { throw 'Unexpected removal boundary' }
    if ((Get-Item -LiteralPath $root -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Transaction root is a link' }
    $pending = [Collections.Generic.Stack[string]]::new()
    $visited = [Collections.Generic.List[string]]::new()
    $skipped = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $retainedDirectories = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $pending.Push($root)
    while ($pending.Count -gt 0) {
        $directory = $pending.Pop()
        $visited.Add($directory)
        foreach ($entry in (Get-ChildItem -LiteralPath $directory -Force)) {
            if (-not $entry.FullName.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Outside removal boundary' }
            if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                Remove-Item -LiteralPath $entry.FullName -Force
            } elseif ($entry.PSIsContainer) {
                $pending.Push($entry.FullName)
            } else {
                try {
                    Remove-Item -LiteralPath $entry.FullName -Force -ErrorAction Stop
                } catch {
                    if ($entry.Name -match '^\.codex-provisioning-[0-9a-f]+\.guard$' -and $entry.Length -eq 0) {
                        [void]$skipped.Add($entry.FullName)
                    } else {
                        throw
                    }
                }
            }
        }
    }
    for ($index=$visited.Count-1; $index -ge 0; $index--) {
        $remaining = @(Get-ChildItem -LiteralPath $visited[$index] -Force)
        # Only zero-byte guards and the directories containing them may remain.
        foreach ($entry in $remaining) {
            if (-not ($skipped.Contains($entry.FullName) -or
                    ($entry.PSIsContainer -and $retainedDirectories.Contains($entry.FullName)))) {
                throw "Unexpected file remains in original data: $($entry.FullName)"
            }
        }
        if ($remaining.Count -gt 0) {
            [void]$retainedDirectories.Add($visited[$index])
        } else {
            Remove-Item -LiteralPath $visited[$index] -Force -ErrorAction Stop
        }
    }
    foreach ($skippedPath in $skipped) { Write-Output $skippedPath }
}

$sourceItem = Get-Item -LiteralPath $source -Force
if ($sourceItem.LinkType -eq 'Junction' -and $sourceItem.Target -eq $destination) {
    Write-Output 'Codex data is already on E.'
    return
}
$users = @(Get-CodexUsers)
if ($InspectOnly) {
    [pscustomobject]@{Source=$source;Destination=$destination;Ready=($users.Count -eq 0);RelatedProcesses=$users.Count} | ConvertTo-Json
    return
}
if ($users.Count -gt 0) { throw 'Please fully exit Codex and stop its background tasks, then run this tool again. No files were moved.' }
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'Run with PowerShell 7 to safely preserve and remove symbolic links.' }
Assert-UnlinkedAncestors $source
Assert-UnlinkedAncestors (Split-Path $destination -Parent)
if ((Get-Volume -DriveLetter E).FileSystem -ne 'NTFS' -or (Get-Volume -DriveLetter E).DriveType -ne 'Fixed') { throw 'E must be a fixed NTFS drive' }
$resumeExisting = Test-Path -LiteralPath $destination
if ($resumeExisting) {
    # A previous copy can be resumed. Require evidence that this exact destination
    # was created by this migration, and never follow a link at the destination.
    $previousLog = Join-Path $evidence 'codex-home-robocopy.log'
    $destinationItem = Get-Item -LiteralPath $destination -Force
    if (-not $destinationItem.PSIsContainer -or
        ($destinationItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        -not (Test-Path -LiteralPath $previousLog)) {
        throw 'Existing destination is not a verified migration copy. Preserve both locations for inspection.'
    }
    $logText = [Text.Encoding]::GetEncoding(936).GetString([IO.File]::ReadAllBytes($previousLog))
    if (-not $logText.Contains($source) -or -not $logText.Contains($destination)) {
        throw 'Existing destination does not match the previous copy log. Preserve both locations for inspection.'
    }
    Write-Output 'Resuming the prior E copy; the C source remains the authority until verification passes.'
}
if (Test-Path -LiteralPath $transaction) { throw 'A previous transaction exists. Preserve it and review the migration record.' }
$sandboxServiceName = 'CodexSandboxService.OpenAI.Codex'
$sandboxService = Get-Service -Name $sandboxServiceName -ErrorAction Stop
$restartSandboxService = $sandboxService.Status -eq [ServiceProcess.ServiceControllerStatus]::Running
if ($restartSandboxService) {
    Write-Output 'Pausing the Codex background sandbox service to release its file lock.'
    Stop-Service -Name $sandboxServiceName -ErrorAction Stop
    (Get-Service -Name $sandboxServiceName).WaitForStatus([ServiceProcess.ServiceControllerStatus]::Stopped,[TimeSpan]::FromSeconds(30))
}
try {
    # The service is a LocalSystem process that may outlive the Codex windows.
    # Check that every provisioning guard is now readable before any large copy.
    foreach ($guard in (Get-ChildItem -LiteralPath $source -Filter '.codex-provisioning-*.guard' -File -Force)) {
        try {
            $guardStream = [IO.File]::Open($guard.FullName,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
            $guardStream.Dispose()
        } catch {
            throw "A provisioning guard is still locked after pausing the sandbox service: $($guard.Name). No files were moved."
        }
    }
New-Item -ItemType Directory -Path $evidence -Force | Out-Null
$manifest = Join-Path $evidence ('codex-home-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-manifest.json')
Write-Output 'Step 1/4: checking original files. Keep Codex closed.'
& $python $verifier manifest $source $manifest --allow-git --allow-links
if ($LASTEXITCODE -ne 0) { throw 'Original manifest failed; source was not changed' }
$data = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
$bytes = [long]0
foreach ($property in $data.files.PSObject.Properties) { $bytes += [long]$property.Value[0] }
$guardNames = [Collections.Generic.List[string]]::new()
foreach ($property in $data.files.PSObject.Properties) {
    if ([IO.Path]::GetFileName($property.Name) -match '^\.codex-provisioning-[0-9a-f]+\.guard$') {
        if ([long]$property.Value[0] -ne 0) { throw "Provisioning guard is not empty: $($property.Name)" }
        $guardNames.Add($property.Name)
    }
}
if ((Get-PSDrive E).Free -lt $bytes + 2GB) { throw 'E does not have enough free space' }
if (@(Get-CodexUsers).Count -gt 0) { throw 'Codex restarted; migration stopped before copying' }
New-Item -ItemType Directory -Path $destination -Force | Out-Null
if ($resumeExisting) {
    # The first copy already established this protected root ACL. Re-applying it
    # through Set-Acl requests SeSecurityPrivilege on an existing NTFS directory.
    $destinationRules = (Get-Acl -LiteralPath $destination).Access
    foreach ($account in @('SPQ\spq','NT AUTHORITY\SYSTEM','BUILTIN\Administrators')) {
        if (-not @($destinationRules | Where-Object {
            $_.IdentityReference.Value -eq $account -and
            $_.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
            ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq [Security.AccessControl.FileSystemRights]::FullControl
        }).Count) { throw "Destination root has insufficient access for $account; preserve both copies." }
    }
    if (-not @($destinationRules | Where-Object {
        $_.IdentityReference.Value -eq 'SPQ\CodexSandboxUsers' -and
        $_.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
        ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::ReadAndExecute) -eq [Security.AccessControl.FileSystemRights]::ReadAndExecute
    }).Count) { throw 'Destination root lacks Codex sandbox read access; preserve both copies.' }
} else {
    $acl = Get-Acl -LiteralPath $destination
    $sourceAccess=(Get-Acl -LiteralPath $source).GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Access)
    $acl.SetSecurityDescriptorSddlForm($sourceAccess,[Security.AccessControl.AccessControlSections]::Access)
    $acl.SetAccessRuleProtection($true,$true)
    Set-Acl -LiteralPath $destination -AclObject $acl
}
Write-Output 'Step 2/4: copying to E; the C copy remains intact.'
$copyLog = Join-Path $evidence 'codex-home-robocopy.log'
& robocopy.exe $source $destination /E /PURGE /COPY:DAT /DCOPY:DAT /SJ /SL /R:1 /W:1 /MT:8 /NP /NFL /NDL /XF '.codex-provisioning-*.guard' "/LOG:$copyLog"
if ($LASTEXITCODE -ge 8) { throw 'Copy failed. Original C data remains intact; review the log before retrying.' }
foreach ($guardName in $guardNames) {
    $sourceGuard = Join-Path $source $guardName
    $destinationGuard = Join-Path $destination $guardName
    if (-not (Test-Path -LiteralPath $destinationGuard)) {
        [IO.File]::WriteAllBytes($destinationGuard,[byte[]]@())
    }
    if ((Get-Item -LiteralPath $destinationGuard -Force).Length -ne 0) { throw "Copied guard is not empty: $guardName" }
    (Get-Item -LiteralPath $destinationGuard -Force).LastWriteTimeUtc = (Get-Item -LiteralPath $sourceGuard -Force).LastWriteTimeUtc
}
Write-Output 'Step 3/4: verifying all copied files and checking the source has not changed.'
& $python $verifier verify $destination $manifest --allow-git --allow-links
if ($LASTEXITCODE -ne 0) { throw 'Destination verification failed; original C data remains intact' }
& $python $verifier verify $source $manifest --allow-git --allow-links
if ($LASTEXITCODE -ne 0) { throw 'Source changed; original C data remains intact' }
if (@(Get-CodexUsers).Count -gt 0) { throw 'Codex restarted; source was not switched' }
Write-Output 'Step 4/4: preserving the original C path and releasing its disk space.'
Rename-Item -LiteralPath $source -NewName '.codex-migration-source'
try {
    New-Item -ItemType Junction -Path $source -Target $destination | Out-Null
} catch {
    if (-not (Test-Path -LiteralPath $source)) { Rename-Item -LiteralPath $transaction -NewName '.codex' }
    throw
}
$link = Get-Item -LiteralPath $source -Force
if ($link.LinkType -ne 'Junction' -or $link.Target -ne $destination) { throw 'Original path restoration requires inspection; both copies were preserved' }
$result = [ordered]@{source=$source;destination=$destination;bytes=$bytes;verified=$true;status='switched';manifest=$manifest;date=(Get-Date -Format o)}
$result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $evidence 'codex-home-result.json') -Encoding utf8
$remainingGuards = @(Remove-VerifiedOriginal)
$result.status=if ($remainingGuards.Count -eq 0) { 'complete' } else { 'complete_with_zero_byte_markers' }
$result.remainingZeroByteMarkers=$remainingGuards.Count
$result.freeC=(Get-PSDrive C).Free
$result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $evidence 'codex-home-result.json') -Encoding utf8
Write-Output "Completed. Original path now stores data on E. Protected zero-byte markers left on C: $($remainingGuards.Count). You can reopen Codex."
} finally {
    if ($restartSandboxService) {
        if ((Get-Service -Name $sandboxServiceName).Status -ne [ServiceProcess.ServiceControllerStatus]::Running) {
            Start-Service -Name $sandboxServiceName -ErrorAction Stop
            (Get-Service -Name $sandboxServiceName).WaitForStatus([ServiceProcess.ServiceControllerStatus]::Running,[TimeSpan]::FromSeconds(30))
        }
        Write-Output 'Codex background sandbox service is running again.'
    }
}
