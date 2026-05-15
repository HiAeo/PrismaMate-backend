"""
PrismaMate 棱镜 - API v1 路由入口
"""

from fastapi import APIRouter

from app.api.v1 import auth, tasks, reports, users, detect, admin

api_router = APIRouter()

# 注册各模块路由
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["检测任务"])
api_router.include_router(reports.router, prefix="/reports", tags=["报告"])
api_router.include_router(users.router, prefix="/user", tags=["用户"])
api_router.include_router(detect.router, prefix="/detect", tags=["极简检测"])
api_router.include_router(admin.router, prefix="/admin", tags=["管理"])
