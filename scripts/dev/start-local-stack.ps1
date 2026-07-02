[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$RuntimeRoot = Join-Path $RepoRoot ".runtime"
$LogRoot = Join-Path $RuntimeRoot "logs"
$PidRoot = Join-Path $RuntimeRoot "pids"
$Python = "D:\Anaconda3\envs\ai-content-ops\python.exe"
$ApiRoot = Join-Path $RepoRoot "apps\api"
$WebRoot = Join-Path $RepoRoot "apps\web"
$ApiPort = 8000
$WebPortMin = 5173
$WebPortMax = 5185

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
New-Item -ItemType Directory -Force -Path $PidRoot | Out-Null

function Test-PidRunning {
    param([string]$PidFile)

    if (-not (Test-Path $PidFile)) {
        return $false
    }

    $rawPid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if (-not $rawPid) {
        return $false
    }

    $process = Get-Process -Id ([int]$rawPid) -ErrorAction SilentlyContinue
    return $null -ne $process
}

function Save-Pid {
    param(
        [string]$PidFile,
        [int]$ProcessId
    )

    Set-Content -Path $PidFile -Value $ProcessId -Encoding ascii
}

function Get-ListeningPid {
    param([int]$Port)

    $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $connection) {
        return $null
    }
    return [int]$connection.OwningProcess
}

function Test-UrlReady {
    param(
        [string]$Url,
        [int]$Attempts = 15,
        [int]$DelaySeconds = 1
    )

    for ($attempt = 0; $attempt -lt $Attempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        } catch {
            Start-Sleep -Seconds $DelaySeconds
        }
    }

    return $false
}

function Find-FreePort {
    param(
        [int]$StartPort,
        [int]$EndPort
    )

    for ($port = $StartPort; $port -le $EndPort; $port++) {
        if (-not (Get-ListeningPid -Port $port)) {
            return $port
        }
    }

    throw "No free port found between $StartPort and $EndPort."
}

function Start-Api {
    $pidFile = Join-Path $PidRoot "api.pid"
    $listeningPid = Get-ListeningPid -Port $ApiPort

    if ($listeningPid -and (Test-UrlReady -Url "http://127.0.0.1:$ApiPort/health" -Attempts 2 -DelaySeconds 1)) {
        Save-Pid -PidFile $pidFile -ProcessId $listeningPid
        return
    }

    if (Test-PidRunning -PidFile $pidFile) {
        return
    }

    $process = Start-Process `
        -FilePath $Python `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$ApiPort" `
        -WorkingDirectory $ApiRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogRoot "api.out.log") `
        -RedirectStandardError (Join-Path $LogRoot "api.err.log") `
        -PassThru

    Save-Pid -PidFile $pidFile -ProcessId $process.Id

    if (-not (Test-UrlReady -Url "http://127.0.0.1:$ApiPort/health")) {
        throw "API did not become ready on port $ApiPort."
    }
}

function Start-Worker {
    $pidFile = Join-Path $PidRoot "worker.pid"
    $workerArguments = @(
        "-m", "celery",
        "-A", "app.tasks.celery_app:celery_app",
        "worker",
        "--loglevel=info",
        "--concurrency=1"
    )

    if ($env:OS -like "*Windows*") {
        $workerArguments += "--pool=solo"
    }

    $existing = Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -eq "python.exe" -and
            $_.CommandLine -like "*-m celery*" -and
            $_.CommandLine -like "*app.tasks.celery_app:celery_app*" -and
            $_.CommandLine -like "*worker*"
        } |
        Select-Object -First 1

    if ($existing) {
        Save-Pid -PidFile $pidFile -ProcessId $existing.ProcessId
        return
    }

    if (Test-PidRunning -PidFile $pidFile) {
        return
    }

    $process = Start-Process `
        -FilePath $Python `
        -ArgumentList $workerArguments `
        -WorkingDirectory $ApiRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogRoot "worker.out.log") `
        -RedirectStandardError (Join-Path $LogRoot "worker.err.log") `
        -PassThru

    Save-Pid -PidFile $pidFile -ProcessId $process.Id
    Start-Sleep -Seconds 5
}

function Start-Web {
    $pidFile = Join-Path $PidRoot "web.pid"
    $portFile = Join-Path $PidRoot "web.port"

    if ((Test-PidRunning -PidFile $pidFile) -and (Test-Path $portFile)) {
        $currentPort = [int](Get-Content $portFile)
        if (Test-UrlReady -Url "http://127.0.0.1:$currentPort" -Attempts 2 -DelaySeconds 1) {
            return $currentPort
        }
    }

    $webPort = Find-FreePort -StartPort $WebPortMin -EndPort $WebPortMax
    $process = Start-Process `
        -FilePath "cmd.exe" `
        -ArgumentList "/c", "npm run dev -- --host 127.0.0.1 --port $webPort" `
        -WorkingDirectory $WebRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogRoot "web.out.log") `
        -RedirectStandardError (Join-Path $LogRoot "web.err.log") `
        -PassThru

    Save-Pid -PidFile $pidFile -ProcessId $process.Id
    Set-Content -Path $portFile -Value $webPort -Encoding ascii

    if (-not (Test-UrlReady -Url "http://127.0.0.1:$webPort")) {
        throw "Web dev server did not become ready on port $webPort."
    }

    return $webPort
}

Write-Host "Starting local test stack..."
powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "start-local-infra.ps1")
Start-Api
Start-Worker
$webPort = Start-Web

Write-Host ""
Write-Host "Local test stack is ready."
Write-Host "Open the page here:"
Write-Host "http://127.0.0.1:$webPort"
Write-Host ""
Write-Host "Health:"
Write-Host "- API : http://127.0.0.1:$ApiPort/health"
Write-Host "- Web : http://127.0.0.1:$webPort"
