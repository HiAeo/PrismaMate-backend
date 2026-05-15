#!/usr/bin/env pwsh
# ============================================================
# PrismaMate 棱镜 - 后端生产启动脚本 (Windows PowerShell)
# ============================================================
# 用法: .\start_backend.ps1
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PrismaMate 棱镜 - 后端启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 获取脚本目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 检查虚拟环境
$VenvDir = "venv"
if (-not (Test-Path "$VenvDir\Scripts\python.exe")) {
    Write-Host "错误: 虚拟环境不存在，正在创建..." -ForegroundColor Red
    python -m venv $VenvDir
    & "$VenvDir\Scripts\pip.exe" install -r requirements.txt
}

# 检查环境变量文件
if (-not (Test-Path ".env")) {
    Write-Host "警告: .env 文件不存在，正在创建..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "请编辑 .env 文件配置您的 API 密钥" -ForegroundColor Yellow
}

# 检查 API Key
$envFile = Get-Content ".env" -Raw -ErrorAction SilentlyContinue
if ($envFile -notmatch "DEEPSEEK_API_KEY=sk-" -and $envFile -notmatch "DEEPSEEK_API_KEY=sk") {
    Write-Host "警告: DEEPSEEK_API_KEY 未配置，请确保已在 .env 中设置" -ForegroundColor Yellow
}

# 激活虚拟环境
Write-Host "激活虚拟环境..." -ForegroundColor Green
& "$VenvDir\Scripts\Activate.ps1" 2>$null
if ($LASTEXITCODE -ne 0) {
    # 如果激活脚本失败，手动设置路径
    $env:PATH = "$ScriptDir\$VenvDir\Scripts;$env:PATH"
    $env:VIRTUAL_ENV = "$ScriptDir\$VenvDir"
}

# 启动服务
Write-Host ""
Write-Host "启动后端服务 (生产模式)..." -ForegroundColor Green
Write-Host "API 文档: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
