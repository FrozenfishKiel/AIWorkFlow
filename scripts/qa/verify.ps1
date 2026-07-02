[CmdletBinding()]
param(
    [ValidateSet("all", "api", "web")]
    [string]$Scope = "all"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ProjectPython = "D:\Anaconda3\envs\ai-content-ops\python.exe"
$ApiRoot = Join-Path $RepoRoot "apps\api"
$WebRoot = Join-Path $RepoRoot "apps\web"
$InfraRoot = Join-Path $RepoRoot "infra"
$AcceptanceRoot = Join-Path $RepoRoot "tests\acceptance"
$Failures = @()

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host "==> $Name"
    try {
        & $Action
        Write-Host "PASS: $Name"
    } catch {
        Write-Host "FAIL: $Name"
        Write-Host $_
        $script:Failures += $Name
    }
}

function Test-AnyFile {
    param(
        [string[]]$Paths,
        [string[]]$Includes
    )

    foreach ($Path in $Paths) {
        if (-not (Test-Path $Path)) {
            continue
        }

        $Matches = Get-ChildItem -Path $Path -Recurse -File -Include $Includes -ErrorAction SilentlyContinue
        if ($Matches) {
            return $true
        }
    }

    return $false
}

function Invoke-ComposeCheck {
    Invoke-Step "Docker compose config" {
        docker compose -f (Join-Path $InfraRoot "docker-compose.yml") config
        if ($LASTEXITCODE -ne 0) { throw "compose config failed" }
    }

    Invoke-Step "Docker compose prod override config" {
        docker compose `
            -f (Join-Path $InfraRoot "docker-compose.yml") `
            -f (Join-Path $InfraRoot "docker-compose.prod.yml") `
            config
        if ($LASTEXITCODE -ne 0) { throw "compose prod override config failed" }
    }
}

function Invoke-CurrentDocChecks {
    if (-not (Test-Path $ProjectPython)) {
        throw "Project Python not found: $ProjectPython"
    }

    Push-Location $ApiRoot
    try {
        Invoke-Step "Current doc drift check" {
            & $ProjectPython -m pytest tests/unit/test_current_docs_contract.py -q
            if ($LASTEXITCODE -ne 0) { throw "current doc contract test failed" }
        }
    } finally {
        Pop-Location
    }
}

function Invoke-ApiChecks {
    if (-not (Test-Path $ProjectPython)) {
        throw "Project Python not found: $ProjectPython"
    }

    Push-Location $ApiRoot
    try {
        Invoke-Step "API bytecode compile" {
            & $ProjectPython -m compileall app
            if ($LASTEXITCODE -ne 0) { throw "compileall failed" }
        }

        Invoke-Step "API import smoke" {
            & $ProjectPython -c "from app.main import app; print(app.title); print(app.version)"
            if ($LASTEXITCODE -ne 0) { throw "FastAPI import smoke failed" }
        }

        if (Test-AnyFile -Paths @((Join-Path $ApiRoot "tests")) -Includes @("test_*.py", "*_test.py")) {
            Invoke-Step "API pytest" {
                & $ProjectPython -m pytest tests -q
                if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
            }
        } else {
            Write-Host "SKIP: API pytest (no test files detected)"
        }
    } finally {
        Pop-Location
    }
}

function Invoke-AcceptanceChecks {
    if (-not (Test-Path $ProjectPython)) {
        throw "Project Python not found: $ProjectPython"
    }

    $HasAcceptanceTests = Test-AnyFile -Paths @($AcceptanceRoot) -Includes @("test_*.py", "*_test.py")
    if (-not $HasAcceptanceTests) {
        Write-Host "SKIP: Root acceptance pytest (no acceptance test files detected)"
        return
    }

    Push-Location $RepoRoot
    try {
        Invoke-Step "Root acceptance pytest" {
            & $ProjectPython -m pytest tests/acceptance -q
            if ($LASTEXITCODE -ne 0) { throw "root acceptance pytest failed" }
        }
    } finally {
        Pop-Location
    }
}

function Invoke-WebChecks {
    Push-Location $WebRoot
    try {
        Invoke-Step "Web build" {
            npm run build
            if ($LASTEXITCODE -ne 0) { throw "web build failed" }
        }

        $HasWebTests = Test-AnyFile -Paths @(
            (Join-Path $WebRoot "tests"),
            (Join-Path $WebRoot "src")
        ) -Includes @("*.test.ts", "*.test.tsx", "*.spec.ts", "*.spec.tsx")

        if ($HasWebTests) {
            Invoke-Step "Web test" {
                npm run test -- --run
                if ($LASTEXITCODE -ne 0) { throw "web tests failed" }
            }
        } else {
            Write-Host "SKIP: Web test (no test files detected)"
        }
    } finally {
        Pop-Location
    }
}

Write-Host "Repository verification"
Write-Host "Root : $RepoRoot"
Write-Host "Scope: $Scope"

switch ($Scope) {
    "api" {
        Invoke-ComposeCheck
        Invoke-CurrentDocChecks
        Invoke-ApiChecks
        Invoke-AcceptanceChecks
    }
    "web" {
        Invoke-WebChecks
    }
    "all" {
        Invoke-ComposeCheck
        Invoke-CurrentDocChecks
        Invoke-ApiChecks
        Invoke-AcceptanceChecks
        Invoke-WebChecks
    }
}

if ($Failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Verification failed:"
    $Failures | ForEach-Object { Write-Host "- $_" }
    exit 1
}

Write-Host ""
Write-Host "Verification completed successfully for scope: $Scope"
exit 0
