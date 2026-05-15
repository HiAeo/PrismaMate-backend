"""
PrismaMate 棱镜 - FastAPI 应用入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import MVP_MODE

# 创建 FastAPI 应用
app = FastAPI(
    title="PrismaMate 棱镜 API",
    description="独立的第三方 GEO 效果检测认证平台",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "PrismaMate 棱镜 API",
        "version": "1.0.0",
        "status": "running",
        "mvp_mode": MVP_MODE
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "mvp_mode": MVP_MODE
    }
