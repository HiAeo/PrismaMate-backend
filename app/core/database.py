"""
PrismaMate 棱镜 - 数据库连接模块（Phase 1 MVP 简化版）

Phase 1 MVP 阶段不依赖数据库，使用内存存储。
数据库相关功能将在 Phase 2 添加。
"""

import os
from typing import Generator, Optional, Any

# MVP 模式标志：True 时不使用数据库
MVP_MODE = True

if not MVP_MODE:
    # 原有 PostgreSQL 代码（Phase 2 启用）
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker, declarative_base

    from app.core.config import get_settings

    settings = get_settings()

    # 异步引擎（用于 FastAPI）
    async_engine = create_async_engine(
        settings.database.url,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

    # 同步引擎（用于 Alembic 迁移）
    sync_engine = create_engine(
        settings.database.sync_url,
        echo=settings.DEBUG,
        pool_pre_ping=True,
    )

    # 异步会话工厂
    AsyncSessionLocal = sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # 同步会话工厂（用于 Celery）
    SyncSessionLocal = sessionmaker(
        bind=sync_engine,
        autocommit=False,
        autoflush=False,
    )

    # 声明基类
    Base = declarative_base()

    async def get_db() -> AsyncSession:
        """获取数据库会话的依赖注入函数"""
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    def get_sync_db():
        """获取同步数据库会话（用于 Celery）"""
        db = SyncSessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

else:
    # MVP 模式：空实现
    # 不创建任何数据库连接
    Base = None

    class MockSession:
        """模拟数据库会话"""
        async def commit(self):
            pass
        async def rollback(self):
            pass
        async def close(self):
            pass
        async def execute(self, *args, **kwargs):
            return MockResult()
        def add(self, *args, **kwargs):
            pass
        async def refresh(self, *args, **kwargs):
            pass

    class MockResult:
        def scalar_one_or_none(self):
            return None
        def scalars(self):
            return MockScalars()
        def scalar(self):
            return None

    class MockScalars:
        def all(self):
            return []

    async def get_db() -> Generator:
        """MVP 模式：返回模拟会话"""
        yield MockSession()

    def get_sync_db():
        """MVP 模式：返回模拟会话"""
        yield MockSession()


class InMemoryStore:
    """
    MVP 阶段内存数据存储
    替代 PostgreSQL 的临时方案
    """
    _users: dict = {}
    _reports: dict = {}
    _tasks: dict = {}

    @classmethod
    def reset(cls):
        """重置所有数据"""
        cls._users.clear()
        cls._reports.clear()
        cls._tasks.clear()

    # 用户操作
    @classmethod
    def get_user(cls, user_id: str):
        return cls._users.get(user_id)

    @classmethod
    def get_user_by_email(cls, email: str):
        for user in cls._users.values():
            if user.get("email") == email:
                return user
        return None

    @classmethod
    def create_user(cls, user_id: str, user_data: dict):
        cls._users[user_id] = user_data

    @classmethod
    def update_user(cls, user_id: str, user_data: dict):
        if user_id in cls._users:
            cls._users[user_id].update(user_data)

    # 报告操作
    @classmethod
    def save_report(cls, report_id: str, report_data: dict):
        cls._reports[report_id] = report_data

    @classmethod
    def get_report(cls, report_id: str):
        return cls._reports.get(report_id)

    @classmethod
    def get_reports_by_user(cls, user_id: str):
        return [
            r for r in cls._reports.values()
            if r.get("user_id") == user_id
        ]

    # 任务操作
    @classmethod
    def save_task(cls, task_id: str, task_data: dict):
        cls._tasks[task_id] = task_data

    @classmethod
    def get_task(cls, task_id: str):
        return cls._tasks.get(task_id)

    @classmethod
    def get_tasks_by_user(cls, user_id: str):
        return [
            t for t in cls._tasks.values()
            if t.get("user_id") == user_id
        ]


# 导出
__all__ = ["get_db", "get_sync_db", "Base", "InMemoryStore", "MVP_MODE"]
