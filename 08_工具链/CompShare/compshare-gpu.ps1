param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("status", "start", "stop")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$instanceId = "cpod-1tz67igx5ijj"
$compshare = "C:\Users\spq\AppData\Roaming\Python\Python311\Scripts\compshare.exe"

if (-not (Test-Path -LiteralPath $compshare)) {
    throw "CompShare CLI not found: $compshare"
}

function Invoke-CompShare {
    param([string[]]$Arguments)
    & $compshare --json @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "CompShare command failed with exit code $LASTEXITCODE"
    }
}

switch ($Action) {
    "status" {
        Invoke-CompShare @("instance", "show", $instanceId, "--status", "--spec", "--billing")
    }
    "start" {
        Invoke-CompShare @("instance", "start", $instanceId, "--timeout", "600")
        Invoke-CompShare @("instance", "wait", $instanceId, "--state", "Running", "--timeout", "600")
        Invoke-CompShare @("instance", "show", $instanceId, "--status", "--spec", "--billing")
    }
    "stop" {
        Invoke-CompShare @("instance", "stop", $instanceId, "--yes", "--timeout", "600")
        Invoke-CompShare @("instance", "wait", $instanceId, "--state", "Stopped", "--timeout", "600")
        Invoke-CompShare @("instance", "show", $instanceId, "--status", "--spec", "--billing")
    }
}
