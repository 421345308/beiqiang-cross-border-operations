$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
try {
    $taskState = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/api/health' -TimeoutSec 2
} catch {
    $taskState = $null
}
if ($taskState) {
    if ($taskState.name -eq '电商商品与订单管理系统' -and $taskState.demo -eq $true) {
        Write-Host '演示系统已运行，请在浏览器打开 http://127.0.0.1:8766/'
        return
    }
    throw '8766端口正运行其他模式或程序，请先核对。'
}
Write-Host '正在启动演示。数据仅供功能验证。'
python -X utf8 app.py --demo
