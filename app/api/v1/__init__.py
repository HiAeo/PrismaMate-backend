"""
PrismaMate 棱镜 - API v1 路由入口
"""

from fastapi import APIRouter

from app.api.v1 import auth, tasks, reports, users, detect, admin, health_check, geo_verification, superadmin, subscription

api_router = APIRouter()

# 注册各模块路由
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["检测任务"])
api_router.include_router(reports.router, prefix="/reports", tags=["报告"])
api_router.include_router(users.router, prefix="/user", tags=["用户"])
api_router.include_router(detect.router, prefix="/detect", tags=["极简检测"])
api_router.include_router(admin.router, prefix="/admin", tags=["平台管理"])  # 平台冷却、冒烟测试
api_router.include_router(health_check.router, prefix="/health-check", tags=["体检模板"])  # V3.0 健康检查模板
api_router.include_router(geo_verification.router, prefix="/geo-verification", tags=["GEO验证"])  # V3.0 Phase 2 GEO验证

# Phase 3 订阅体系
api_router.include_router(superadmin.router, prefix="", tags=["超级管理员"])  # 管理员后台（路由已有 /superadmin 前缀）
api_router.include_router(subscription.router, prefix="", tags=["订阅管理"])  # 用户端订阅（路由已有 /subscription 前缀）
