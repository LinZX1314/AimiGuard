param(
    [switch]$SkipBackend,
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
    Write-Host $Title -ForegroundColor Yellow
    Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
}

function Invoke-Checked {
    param(
        [string]$Title,
        [scriptblock]$Action
    )

    Write-Host "[RUN] $Title" -ForegroundColor Yellow
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Title failed with exit code $LASTEXITCODE"
    }
    Write-Host "[OK] $Title" -ForegroundColor Green
}

function Get-PythonCommand {
    $venvPython = Join-Path $ProjectRoot "backend\venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }
    return "python"
}

$pythonCmd = Get-PythonCommand
$frontendPath = Join-Path $ProjectRoot "frontend"
$frontendNodeModules = Join-Path $frontendPath "node_modules"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Aimiguan local offline verification v1.0" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Invoke-Checked "Check Python" {
    & $pythonCmd --version
}

Invoke-Checked "Check Node.js" {
    node --version
}

if (-not (Test-Path $frontendNodeModules) -and -not $SkipFrontend) {
    throw "Missing frontend\\node_modules. Run npm install or npm ci while online first."
}

if (-not $SkipBackend) {
    Write-Section "Backend verification"

    Invoke-Checked "Compile backend Python sources" {
        & $pythonCmd -m compileall backend
    }

    $previousTesting = $env:TESTING
    try {
        $env:TESTING = "1"
        Invoke-Checked "Run backend regression and workflow suite" {
            & $pythonCmd -m pytest tests/test_step8_9_full.py tests/test_td05_push.py tests/test_workflow_dsl.py tests/test_workflow_m1_02.py tests/test_workflow_m1_03_api.py tests/test_workflow_m2_02_validator.py tests/test_workflow_m2_03_release_api.py tests/test_workflow_m2_04_rbac.py tests/test_workflow_m3_01_runtime.py tests/test_workflow_m3_02_defense_runtime.py tests/test_workflow_m3_03_rollout.py tests/test_workflow_m4_01_scan_runtime.py tests/test_workflow_m4_02_monitoring_api.py tests/test_workflow_m4_03_replay_debug.py -v --tb=short
        }
    } finally {
        $env:TESTING = $previousTesting
    }
}

if (-not $SkipFrontend) {
    Write-Section "Frontend verification"

    Push-Location $frontendPath
    try {
        Invoke-Checked "Run frontend typecheck" {
            npx vue-tsc --noEmit
        }

        Invoke-Checked "Run frontend production build" {
            npx vite build
        }
    } finally {
        Pop-Location
    }
}

Write-Section "Verification completed"
Write-Host "[OK] Local offline verification passed" -ForegroundColor Green
