#!/usr/bin/env pwsh
# PrismaMate 棱镜 - 后端启动脚本
# 双击运行此脚本启动后端服务

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PrismaMate 棱镜 - 后端服务" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 设置工作目录
Set-Location $PSScriptRoot

# 激活虚拟环境并启动
Write-Host "正在启动服务..." -ForegroundColor Green
& ".\venv\Scripts\python.exe" -c "from dotenv import load_dotenv; load_dotenv(); import uvicorn; from app.main import app; print('后端启动成功!'); print('API 文档: http://localhost:8000/docs'); uvicorn.run(app, host='0.0.0.0', port=8000)"

Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
