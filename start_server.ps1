cd "d:\PrismaMate专用文件夹\prismamate-backend"
Write-Host "========== PrismaMate 后端 ==========" -ForegroundColor Cyan
Write-Host "启动中..." -ForegroundColor Yellow
& "d:\PrismaMate专用文件夹\prismamate-backend\venv\Scripts\python.exe" -c "from dotenv import load_dotenv; load_dotenv(); import uvicorn; from app.main import app; print('API文档: http://localhost:8002/docs'); uvicorn.run(app, host='0.0.0.0', port=8002)"
