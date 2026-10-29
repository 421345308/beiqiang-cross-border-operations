[CmdletBinding()]
param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$localUrl = 'http://127.0.0.1:8765'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$statePath = Join-Path $PSScriptRoot '.local'
function Get-WorkbenchHealth {
    try { return Invoke-RestMethod -Uri "$localUrl/api/health" -TimeoutSec 2 -UseBasicParsing } catch { return $null }
}
function Test-WorkbenchIdentity($health) {
    return ($health -and $health.ok -eq $true -and $health.app -eq 'beiqiang-workbench' -and [string]::Equals([string]$health.root, $projectRoot, [StringComparison]::OrdinalIgnoreCase))
}
function Test-PortOccupied {
    $client = New-Object Net.Sockets.TcpClient
    try { $client.Connect('127.0.0.1', 8765); return $true } catch { return $false } finally { $client.Dispose() }
}
try {
    $health = Get-WorkbenchHealth
    if (-not (Test-WorkbenchIdentity $health)) {
        if (Test-PortOccupied) { throw '8765端口已被其他服务或其他目录的工作台占用。请先确认并关闭该服务，再启动本工作台。' }
        $python = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        $pythonArgs = @()
        if (-not $python -or $python.Source -like '*\Microsoft\WindowsApps\*') {
            $python = Get-Command py -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
            $pythonArgs = @('-3')
        }
        if (-not $python) { throw '找不到Python。请安装Python 3.10或更新版本并加入PATH，然后重新启动。' }
        & $python.Source @pythonArgs -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'
        if ($LASTEXITCODE -ne 0) { throw 'Python未能运行或版本低于3.10。请检查本机Python安装。' }
        New-Item -ItemType Directory -Path $statePath -Force | Out-Null
        $outLog = Join-Path $statePath 'server.stdout.log'
        $errLog = Join-Path $statePath 'server.stderr.log'
        $serverPath = Join-Path $PSScriptRoot 'server.py'
        $arguments = @($pythonArgs) + @('-X', 'utf8', ('"{0}"' -f $serverPath), '--port', '8765', '--root', ('"{0}"' -f $projectRoot))
        $service = Start-Process -FilePath $python.Source -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru
        $deadline = (Get-Date).AddSeconds(15)
        do {
            $health = Get-WorkbenchHealth
            if (Test-WorkbenchIdentity $health) { break }
            $service.Refresh()
            if ($service.HasExited) { throw "工作台启动失败。请查看日志：$errLog" }
            Start-Sleep -Milliseconds 250
        } while ((Get-Date) -lt $deadline)
        if (-not (Test-WorkbenchIdentity $health)) { throw "工作台未能及时就绪。请查看日志：$errLog" }
    }
    Write-Output "LocalURL: $localUrl"
    Write-Output '工作台已在本机后台运行。关闭浏览器不会停止服务；重复启动会打开现有工作台。'
    if (-not $NoBrowser) { Start-Process $localUrl }
    exit 0
} catch {
    Write-Host ("启动失败：" + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
