# Aimiguan 开发环境一键启动脚本
# 功能：初始化数据库 + 启动后端 + 启动前端

param(
    [switch]$PrepareOnly,
    [switch]$Verify,
    [switch]$InstallBackendDependencies,
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendPath = Join-Path $ProjectRoot "backend"
$FrontendPath = Join-Path $ProjectRoot "frontend"
$BackendPort = 8000
$FrontendPort = 3000
$BackendUrl = "http://localhost:$BackendPort"
$FrontendUrl = "http://localhost:$FrontendPort"
$BackendHealthUrl = "$BackendUrl/api/health"
$BackendRequirementsPath = Join-Path $BackendPath "requirements.txt"
$BackendRequirementsStamp = Join-Path $BackendPath "venv\.requirements.sha256"

function Test-PortListening {
    param([int]$Port)

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(250)) {
            return $false
        }
        $client.EndConnect($async)
        return $client.Connected
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Wait-ForBackendHealth {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 3
            if ($response.code -eq 0 -and $response.data.status -eq "healthy") {
                return $true
            }
        } catch {
        }
        Start-Sleep -Seconds 1
    }

    return $false
}

function Stop-BackendJob {
    param($Job)

    if ($null -eq $Job) {
        return
    }

    Stop-Job -Job $Job -ErrorAction SilentlyContinue
    Remove-Job -Job $Job -Force -ErrorAction SilentlyContinue
}

Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          Aimiguan 开发环境启动脚本 v1.0                    ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 检查 Python
Write-Host "🔍 检查 Python 环境..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ 未找到 Python，请先安装 Python 3.8+" -ForegroundColor Red
    exit 1
}

# 检查 Node.js
Write-Host "🔍 检查 Node.js 环境..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    Write-Host "✓ Node.js: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ 未找到 Node.js，请先安装 Node.js 16+" -ForegroundColor Red
    exit 1
}

if (-not $PrepareOnly) {
    if (Test-PortListening -Port $BackendPort) {
        Write-Host "✗ 端口 $BackendPort 已被占用，请先关闭现有后端服务" -ForegroundColor Red
        exit 1
    }

    if (Test-PortListening -Port $FrontendPort) {
        Write-Host "✗ 端口 $FrontendPort 已被占用，请先关闭现有前端服务" -ForegroundColor Red
        exit 1
    }
}

# 初始化后端
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "📦 初始化后端..." -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

Set-Location $BackendPath

# 检查并安装依赖
$backendNeedsInstall = $InstallBackendDependencies
if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    Write-Host "🔧 创建虚拟环境..." -ForegroundColor Yellow
    python -m venv venv
    $backendNeedsInstall = $true
}

$currentRequirementsHash = (Get-FileHash $BackendRequirementsPath -Algorithm SHA256).Hash
$storedRequirementsHash = if (Test-Path $BackendRequirementsStamp) {
    (Get-Content $BackendRequirementsStamp -Raw).Trim()
} else {
    ""
}

if (-not $backendNeedsInstall -and $currentRequirementsHash -ne $storedRequirementsHash) {
    Write-Host "🔧 检测到后端依赖清单变化，重新同步依赖..." -ForegroundColor Yellow
    $backendNeedsInstall = $true
}

Write-Host "🔧 激活虚拟环境..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

if ($backendNeedsInstall) {
    Write-Host "🔧 安装/更新依赖..." -ForegroundColor Yellow
    pip install -r requirements.txt -q
    Set-Content -Path $BackendRequirementsStamp -Value $currentRequirementsHash -NoNewline -Encoding utf8
} else {
    Write-Host "✓ 后端依赖已安装" -ForegroundColor Green
}

# 自动生成 .env
$envFile = Join-Path $BackendPath ".env"
$envExample = Join-Path $BackendPath ".env.example"
if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Write-Host "🔧 从 .env.example 生成 .env ..." -ForegroundColor Yellow
        $content = Get-Content $envExample -Raw
        # 生成随机 JWT_SECRET
        $randomBytes = New-Object byte[] 32
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($randomBytes)
        $jwtSecret = [Convert]::ToBase64String($randomBytes)
        $content = $content -replace 'JWT_SECRET=.*', "JWT_SECRET=$jwtSecret"
        Set-Content -Path $envFile -Value $content -Encoding utf8
        Write-Host "✓ .env 已生成（JWT_SECRET 已随机化）" -ForegroundColor Green
    } else {
        Write-Host "⚠️  未找到 .env.example，请手动创建 .env" -ForegroundColor Yellow
    }
} else {
    Write-Host "✓ .env 已存在" -ForegroundColor Green
}

# 初始化数据库
Write-Host "🗄️  初始化数据库..." -ForegroundColor Yellow
$databasePath = Join-Path $BackendPath "aimiguard.db"
if (Test-Path $databasePath) {
    Write-Host "✓ 检测到现有数据库，跳过重建" -ForegroundColor Green
} elseif (Test-Path "init_db.py") {
    python init_db.py
    Write-Host "✓ 数据库初始化完成" -ForegroundColor Green
} else {
    Write-Host "⚠️  未找到 init_db.py，跳过数据库初始化" -ForegroundColor Yellow
}

# 初始化前端
if (-not $SkipFrontend) {
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "📦 初始化前端..." -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

    Set-Location $FrontendPath

    # 自动生成前端 .env
    $feEnvFile = Join-Path $FrontendPath ".env"
    $feEnvExample = Join-Path $FrontendPath ".env.example"
    if (-not (Test-Path $feEnvFile) -and (Test-Path $feEnvExample)) {
        Copy-Item $feEnvExample $feEnvFile
        Write-Host "✓ 前端 .env 已从 .env.example 复制" -ForegroundColor Green
    }

    if (-not (Test-Path "node_modules")) {
        Write-Host "🔧 安装前端依赖..." -ForegroundColor Yellow
        npm install
    } else {
        Write-Host "✓ 前端依赖已安装" -ForegroundColor Green
    }
} else {
    Write-Host ""
    Write-Host "⏭️  跳过前端初始化 (-SkipFrontend)" -ForegroundColor Yellow
}

if ($Verify) {
    Write-Host ""
    Write-Host "🧪 执行本地离线验收..." -ForegroundColor Yellow
    & "$PSScriptRoot\verify.ps1"
}

if ($PrepareOnly) {
    Write-Host ""
    Write-Host "✓ 环境准备完成，已按要求跳过服务启动" -ForegroundColor Green
    exit 0
}

# 启动服务
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🚀 启动服务..." -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "📌 后端服务: $BackendUrl" -ForegroundColor Cyan
Write-Host "📌 API 文档: $BackendUrl/docs" -ForegroundColor Cyan
Write-Host "📌 健康检查: $BackendHealthUrl" -ForegroundColor Cyan
Write-Host "📌 前端服务: $FrontendUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 提示: 按 Ctrl+C 停止所有服务" -ForegroundColor Yellow
Write-Host ""

# 启动后端（后台）
Set-Location $BackendPath
$backendPython = (Resolve-Path ".\venv\Scripts\python.exe").Path
$backendJob = Start-Job -ScriptBlock {
    param($path, $pythonPath)
    Set-Location $path
    & $pythonPath main.py
} -ArgumentList (Get-Location).Path, $backendPython

if (-not (Wait-ForBackendHealth -Url $BackendHealthUrl -TimeoutSeconds 30)) {
    Write-Host "✗ 后端健康检查失败，请检查启动日志" -ForegroundColor Red
    $backendOutput = Receive-Job -Job $backendJob -Keep -ErrorAction SilentlyContinue
    if ($backendOutput) {
        Write-Host ""
        Write-Host "----- Backend Output -----" -ForegroundColor Yellow
        $backendOutput | Out-Host
    }
    Stop-BackendJob -Job $backendJob
    exit 1
}

Write-Host "✓ 后端健康检查通过" -ForegroundColor Green

# 启动前端（前台）
if (-not $SkipFrontend) {
    Set-Location $FrontendPath
    try {
        npm run dev
    } finally {
        Write-Host ""
        Write-Host "🛑 正在停止服务..." -ForegroundColor Yellow
        Stop-BackendJob -Job $backendJob
        Write-Host "✓ 服务已停止" -ForegroundColor Green
    }
} else {
    Write-Host "✓ 仅后端模式，前端已跳过" -ForegroundColor Green
    Write-Host "💡 按 Ctrl+C 停止后端" -ForegroundColor Yellow
    try {
        Wait-Job -Job $backendJob
    } finally {
        Write-Host ""
        Write-Host "🛑 正在停止后端..." -ForegroundColor Yellow
        Stop-BackendJob -Job $backendJob
        Write-Host "✓ 服务已停止" -ForegroundColor Green
    }
}
