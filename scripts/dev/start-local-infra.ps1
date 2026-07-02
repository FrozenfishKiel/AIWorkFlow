[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ComposeFile = Join-Path $RepoRoot "infra\docker-compose.yml"

function Test-ContainerRunning {
    param(
        [string]$Name
    )

    $result = docker inspect -f "{{.State.Running}}" $Name 2>$null
    return ($LASTEXITCODE -eq 0) -and ($result.Trim() -eq "true")
}

function Test-ContainerExists {
    param(
        [string]$Name
    )

    docker inspect $Name 1>$null 2>$null
    return $LASTEXITCODE -eq 0
}

$ServiceMap = @(
    @{ Service = "postgres"; Name = "ai-content-ops-postgres" },
    @{ Service = "redis"; Name = "ai-content-ops-redis" },
    @{ Service = "minio"; Name = "ai-content-ops-minio" }
)

$MissingServices = @()
$StoppedContainers = @()

foreach ($Entry in $ServiceMap) {
    if (Test-ContainerRunning -Name $Entry.Name) {
        continue
    }

    if (Test-ContainerExists -Name $Entry.Name) {
        $StoppedContainers += $Entry.Name
        continue
    }

    $MissingServices += $Entry.Service
}

if ($StoppedContainers.Count -gt 0) {
    Write-Host "Starting existing infra containers: $($StoppedContainers -join ', ')"
    docker start @StoppedContainers
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start existing infra containers."
    }
}

if ($MissingServices.Count -gt 0) {
    Write-Host "Creating missing infra services: $($MissingServices -join ', ')"
    docker compose -f $ComposeFile up -d @MissingServices
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create missing infra services."
    }
}

if ($StoppedContainers.Count -eq 0 -and $MissingServices.Count -eq 0) {
    Write-Host "Infra containers are already running."
}

Write-Host ""
Write-Host "Infra services started."
Write-Host "Next, run API / worker / web locally from:"
Write-Host "- apps/api (uvicorn)"
Write-Host "- apps/api (celery worker)"
Write-Host "- apps/web (vite dev server)"
