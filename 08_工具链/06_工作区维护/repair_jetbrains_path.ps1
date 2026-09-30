$ErrorActionPreference='Stop'
$status='E:\C盘迁移\迁移校验\jetbrains-path-repair.json'
try {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class MigrationPackageCheck {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode)]
    public static extern int GetCurrentPackageFullName(ref UInt32 length, IntPtr packageName);
}
'@
    [uint32]$length=0
    $packageStatus=[MigrationPackageCheck]::GetCurrentPackageFullName([ref]$length,[IntPtr]::Zero)
    if ($packageStatus -ne 15700) { throw "Helper still has an application package identity ($packageStatus); do not create a redirected link" }
    $source='C:\Users\spq\AppData\Local\JetBrains'
    $destination='E:\C盘迁移\JetBrains'
    if (-not (Test-Path -LiteralPath $destination)) { throw 'Verified E data is missing' }
    if (Test-Path -LiteralPath $source) { throw 'Original path exists; preserve it for inspection' }
    New-Item -ItemType Junction -Path $source -Target $destination | Out-Null
    $link=Get-Item -LiteralPath $source -Force
    if ($link.LinkType -ne 'Junction' -or $link.Target -ne $destination) { throw 'Link check failed' }
    $children=@(Get-ChildItem -LiteralPath $source -Force)
    [pscustomobject]@{verified=$true;source=$source;destination=$destination;children=$children.Count;date=(Get-Date -Format o)} | ConvertTo-Json | Set-Content -LiteralPath $status -Encoding utf8
} catch {
    [pscustomobject]@{verified=$false;error=$_.Exception.Message;date=(Get-Date -Format o)} | ConvertTo-Json | Set-Content -LiteralPath $status -Encoding utf8
    exit 1
}
