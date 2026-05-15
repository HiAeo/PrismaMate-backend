# PrismaMate Backend Startup Script
# 使用 UTF-8 with BOM 编码

# 获取脚本所在目录
$ScriptDir = $PSScriptRoot

# 切换到后端目录
Set-Location -Path $ScriptDir

Write-Host "========== PrismaMate Backend ==========" -ForegroundColor Cyan
Write-Host "Starting backend service..." -ForegroundColor Yellow

# 启动 uvicorn
& "$ScriptDir\venv\Scripts\python.exe" -c "from dotenv import load_dotenv; load_dotenv(); import uvicorn; from app.main import app; print('API Docs: http://localhost:8002/docs'); uvicorn.run(app, host='0.0.0.0', port=8002)"
