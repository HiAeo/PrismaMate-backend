"""
PrismaMate 棱镜 - 用户数据内存存储（Phase 1/2 MVP）

使用内存字典存储用户数据，Phase 3 切换到 PostgreSQL
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from app.core.auth import hash_password


class User:
    """用户数据模型"""
    
    def __init__(
        self,
        user_id: str,
        email: str,
        username: str,
        password_hash: str,
        created_at: datetime = None,
        is_active: bool = True
    ):
        self.user_id = user_id
        self.email = email
        self.username = username
        self.password_hash = password_hash
        self.created_at = created_at or datetime.utcnow()
        self.is_active = is_active
    
    def to_dict(self) -> dict:
        """转换为字典（不包含密码）"""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "username": self.username,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active
        }


class Task:
    """检测任务数据模型"""
    
    def __init__(
        self,
        task_id: str,
        user_id: str,
        keywords: List[str],
        brands: List[str],
        platform: str,
        status: str = "pending",
        created_at: datetime = None
    ):
        self.task_id = task_id
        self.user_id = user_id
        self.keywords = keywords
        self.brands = brands
        self.platform = platform
        self.status = status  # pending, running, completed, failed
        self.created_at = created_at or datetime.utcnow()
        self.completed_at = None
        self.report_id = None
        self.error_message = None
    
    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "keywords": self.keywords,
            "brands": self.brands,
            "platform": self.platform,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "report_id": self.report_id,
            "error_message": self.error_message
        }


class Report:
    """报告数据模型"""
    
    def __init__(
        self,
        report_id: str,
        verification_code: str,
        report_hash: str,
        user_id: str,
        task_id: str,
        keywords: List[str],
        platforms: List[str],
        total_mentions: int,
        brand_mentions: List[dict],
        total_citations: int,
        report_html: str = "",
        created_at: datetime = None
    ):
        self.report_id = report_id
        self.verification_code = verification_code
        self.report_hash = report_hash
        self.user_id = user_id
        self.task_id = task_id
        self.keywords = keywords
        self.platforms = platforms
        self.total_mentions = total_mentions
        self.brand_mentions = brand_mentions
        self.total_citations = total_citations
        self.report_html = report_html
        self.created_at = created_at or datetime.utcnow()
    
    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "verification_code": self.verification_code,
            "report_hash": self.report_hash,
            "user_id": self.user_id,
            "task_id": self.task_id,
            "keywords": self.keywords,
            "platforms": self.platforms,
            "total_mentions": self.total_mentions,
            "brand_mentions": self.brand_mentions,
            "total_citations": self.total_citations,
            "created_at": self.created_at.isoformat()
        }


class UserStore:
    """用户数据内存存储"""
    
    def __init__(self):
        # 用户存储: {email: User}
        self._users: Dict[str, User] = {}
        # 用户名存储: {username: User}
        self._users_by_username: Dict[str, User] = {}
        # 任务存储: {task_id: Task}
        self._tasks: Dict[str, Task] = {}
        # 报告存储: {report_id: Report}
        self._reports: Dict[str, Report] = {}
        # 验证码存储: {verification_code: Report}
        self._reports_by_code: Dict[str, Report] = {}
        
        # 初始化一个测试用户
        self._init_demo_user()
    
    def _init_demo_user(self):
        """初始化演示用户"""
        demo_user = User(
            user_id="demo-user-001",
            email="demo@prismamate.com",
            username="demo",
            password_hash=hash_password("demo123"),
            created_at=datetime(2026, 1, 1)
        )
        self._users[demo_user.email] = demo_user
        self._users_by_username[demo_user.username] = demo_user
    
    # ==================== 用户操作 ====================
    
    def create_user(self, email: str, username: str, password: str) -> Optional[User]:
        """
        创建新用户
        
        Args:
            email: 邮箱
            username: 用户名
            password: 明文密码
        
        Returns:
            User 对象，失败返回 None
        """
        # 检查邮箱是否已存在
        if email in self._users:
            return None
        
        # 检查用户名是否已存在
        if username in self._users_by_username:
            return None
        
        # 创建用户
        user = User(
            user_id=f"user-{uuid.uuid4().hex[:12]}",
            email=email,
            username=username,
            password_hash=hash_password(password)
        )
        
        self._users[email] = user
        self._users_by_username[username] = user
        
        return user
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        return self._users.get(email)
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """通过用户ID获取用户"""
        for user in self._users.values():
            if user.user_id == user_id:
                return user
        return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        return self._users_by_username.get(username)
    
    # ==================== 任务操作 ====================
    
    def create_task(
        self,
        user_id: str,
        keywords: List[str],
        brands: List[str],
        platform: str
    ) -> Task:
        """
        创建检测任务
        
        Args:
            user_id: 用户ID
            keywords: 关键词列表
            brands: 品牌列表
            platform: 平台名称
        
        Returns:
            Task 对象
        """
        task = Task(
            task_id=f"task-{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            keywords=keywords,
            brands=brands,
            platform=platform
        )
        self._tasks[task.task_id] = task
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def get_tasks_by_user(self, user_id: str) -> List[Task]:
        """获取用户的所有任务"""
        return [
            task for task in self._tasks.values()
            if task.user_id == user_id
        ]
    
    def update_task(
        self,
        task_id: str,
        status: str = None,
        report_id: str = None,
        error_message: str = None
    ) -> Optional[Task]:
        """更新任务状态"""
        task = self._tasks.get(task_id)
        if task:
            if status:
                task.status = status
                if status == "completed":
                    task.completed_at = datetime.utcnow()
            if report_id:
                task.report_id = report_id
            if error_message:
                task.error_message = error_message
        return task
    
    # ==================== 报告操作 ====================
    
    def create_report(
        self,
        report_id: str,
        verification_code: str,
        report_hash: str,
        user_id: str,
        task_id: str,
        keywords: List[str],
        platforms: List[str],
        total_mentions: int,
        brand_mentions: List[dict],
        total_citations: int,
        report_html: str = ""
    ) -> Report:
        """
        创建报告
        
        Returns:
            Report 对象
        """
        # 统一将验证码转为大写存储
        normalized_code = verification_code.upper()
        
        report = Report(
            report_id=report_id,
            verification_code=normalized_code,
            report_hash=report_hash,
            user_id=user_id,
            task_id=task_id,
            keywords=keywords,
            platforms=platforms,
            total_mentions=total_mentions,
            brand_mentions=brand_mentions,
            total_citations=total_citations,
            report_html=report_html
        )
        self._reports[report_id] = report
        self._reports_by_code[normalized_code] = report
        return report
    
    def get_report(self, report_id: str) -> Optional[Report]:
        """获取报告"""
        return self._reports.get(report_id)
    
    def get_report_by_code(self, code: str) -> Optional[Report]:
        """通过验证码获取报告（大小写不敏感）"""
        # 统一将查询验证码转为大写
        normalized_code = code.upper()
        return self._reports_by_code.get(normalized_code)
    
    def get_reports_by_user(self, user_id: str) -> List[Report]:
        """获取用户的所有报告"""
        return [
            report for report in self._reports.values()
            if report.user_id == user_id
        ]
    
    def get_reports_by_task(self, task_id: str) -> List[Report]:
        """获取任务的所有报告"""
        return [
            report for report in self._reports.values()
            if report.task_id == task_id
        ]
    
    # ==================== 统计 ====================
    
    def get_user_stats(self, user_id: str) -> dict:
        """获取用户统计信息"""
        tasks = self.get_tasks_by_user(user_id)
        reports = self.get_reports_by_user(user_id)
        
        return {
            "total_tasks": len(tasks),
            "completed_tasks": len([t for t in tasks if t.status == "completed"]),
            "total_reports": len(reports),
            "total_mentions": sum(r.total_mentions for r in reports),
            "total_detections": len(reports)  # 每次检测生成一份报告
        }


# 全局用户存储实例
user_store = UserStore()
