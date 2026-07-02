[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$PidRoot = Join-Path $RepoRoot ".runtime\pids"

function Stop-FromPidFile {
    param(
        [string]$Name,
        [string]$PidFile
    )

    if (-not (Test-Path $PidFile)) {
        return
    }

    $rawPid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($rawPid) {
        Get-Process -Id ([int]$rawPid) -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }

    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped $Name"
}

Stop-FromPidFile -Name "web" -PidFile (Join-Path $PidRoot "web.pid")
Stop-FromPidFile -Name "worker" -PidFile (Join-Path $PidRoot "worker.pid")
Stop-FromPidFile -Name "api" -PidFile (Join-Path $PidRoot "api.pid")
Remove-Item (Join-Path $PidRoot "web.port") -Force -ErrorAction SilentlyContinue
