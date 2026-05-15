"""
PrismaMate 棱镜 - 用户数据内存存储（Phase 1/2 MVP）

使用内存字典存储用户数据，Phase 3 切换到 PostgreSQL
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from app.core.auth import hash_password


# ==================== Phase 3 订阅体系数据模型 ====================

# 订阅计划预置数据（不可删除，可编辑）
SUBSCRIPTION_PLANS = [
    {
        "id": "plan_mini",
        "name": "单棱MINI版",
        "monthly_price": 0,
        "yearly_price": 0,
        "monthly_quota": 10,
        "monthly_points": 20,
        "max_keywords": 3,
        "max_platforms": 1,
        "max_competitors": 0,
        "has_pdf_download": False,
        "has_api_access": False,
        "data_retention_days": 7,
        "features": [
            "每月 10 次品牌检测",
            "每日 20 积分",
            "最多 3 个关键词",
            "最多 1 个平台",
            "数据保留 7 天"
        ]
    },
    {
        "id": "plan_max",
        "name": "复棱MAX版",
        "monthly_price": 299,
        "yearly_price": 2999,
        "monthly_quota": 100,
        "monthly_points": 200,
        "max_keywords": 10,
        "max_platforms": 2,
        "max_competitors": 5,
        "has_pdf_download": True,
        "has_api_access": False,
        "data_retention_days": 90,
        "features": [
            "每月 100 次品牌检测",
            "每日 200 积分",
            "最多 10 个关键词",
            "最多 2 个平台",
            "最多 5 个竞品对比",
            "PDF 报告下载",
            "数据保留 90 天"
        ]
    },
    {
        "id": "plan_plus",
        "name": "晶曜PLUS版",
        "monthly_price": 999,
        "yearly_price": 9999,
        "monthly_quota": 500,
        "monthly_points": 1000,
        "max_keywords": 999,
        "max_platforms": 3,
        "max_competitors": 999,
        "has_pdf_download": True,
        "has_api_access": True,
        "data_retention_days": 365,
        "features": [
            "每月 500 次品牌检测",
            "每日 1000 积分",
            "无限关键词",
            "全部 3 个平台",
            "无限竞品对比",
            "PDF 报告下载",
            "API 接口访问",
            "数据保留 365 天",
            "专属客服支持"
        ]
    }
]

# Plan 字典，方便快速查找
PLANS_DICT = {plan["id"]: plan for plan in SUBSCRIPTION_PLANS}


class PointsTransaction:
    """积分流水数据模型"""
    
    def __init__(
        self,
        transaction_id: str,
        user_id: str,
        amount: int,  # 正数增加，负数消耗
        balance_after: int,
        type: str,  # detection/gift/purchase/admin_adjust/subscription_grant
        description: str,
        created_at: datetime = None
    ):
        self.transaction_id = transaction_id
        self.user_id = user_id
        self.amount = amount
        self.balance_after = balance_after
        self.type = type
        self.description = description
        self.created_at = created_at or datetime.utcnow()
    
    def to_dict(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "balance_after": self.balance_after,
            "type": self.type,
            "description": self.description,
            "created_at": self.created_at.isoformat()
        }


class PaymentOrder:
    """支付订单数据模型"""
    
    def __init__(
        self,
        order_id: str,
        user_id: str,
        order_type: str,  # subscription/points
        amount: float,
        plan_id: str = None,
        points_amount: int = 0,
        status: str = "pending",  # pending/paid/refunded
        created_at: datetime = None
    ):
        self.order_id = order_id
        self.user_id = user_id
        self.order_type = order_type
        self.plan_id = plan_id
        self.points_amount = points_amount
        self.amount = amount
        self.status = status
        self.created_at = created_at or datetime.utcnow()
        self.paid_at = None
    
    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "user_id": self.user_id,
            "order_type": self.order_type,
            "plan_id": self.plan_id,
            "points_amount": self.points_amount,
            "amount": self.amount,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "paid_at": self.paid_at.isoformat() if self.paid_at else None
        }


class Admin:
    """管理员账号数据模型"""
    
    def __init__(
        self,
        admin_id: str,
        username: str,
        password_hash: str,
        role: str,  # super_admin/admin
        created_at: datetime = None
    ):
        self.admin_id = admin_id
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.created_at = created_at or datetime.utcnow()
    
    def to_dict(self) -> dict:
        return {
            "admin_id": self.admin_id,
            "username": self.username,
            "role": self.role,
            "created_at": self.created_at.isoformat()
        }


# ==================== 原有数据模型 ====================

class HealthCheckTemplate:
    """体检模板数据模型"""
    
    def __init__(
        self,
        template_id: str,
        user_id: str,
        name: str,
        brands: List[dict],
        keywords: List[str],
        platforms: List[str],
        created_at: datetime = None,
        updated_at: datetime = None,
        last_used_at: datetime = None
    ):
        self.template_id = template_id
        self.user_id = user_id
        self.name = name
        self.brands = brands  # [{"full_name": "华为", "short_names": ["华为", "Huawei"]}]
        self.keywords = keywords
        self.platforms = platforms
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
        self.last_used_at = last_used_at
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "template_id": self.template_id,
            "user_id": self.user_id,
            "name": self.name,
            "brands": self.brands,
            "keywords": self.keywords,
            "platforms": self.platforms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None
        }
    
    def update_last_used(self):
        """更新最后使用时间"""
        self.last_used_at = datetime.utcnow()


class User:
    """用户数据模型（Phase 3 扩展：订阅体系）"""
    
    def __init__(
        self,
        user_id: str,
        email: str,
        username: str,
        password_hash: str,
        created_at: datetime = None,
        is_active: bool = True,
        # Phase 3 新增字段
        plan_id: str = "plan_mini",
        points_balance: int = 50,
        monthly_usage: int = 0,
        subscription_expires_at: datetime = None,
        last_usage_reset_at: datetime = None
    ):
        self.user_id = user_id
        self.email = email
        self.username = username
        self.password_hash = password_hash
        self.created_at = created_at or datetime.utcnow()
        self.is_active = is_active
        # Phase 3 新增字段
        self.plan_id = plan_id
        self.points_balance = points_balance
        self.monthly_usage = monthly_usage
        self.subscription_expires_at = subscription_expires_at  # 免费版永不过期
        self.last_usage_reset_at = last_usage_reset_at or datetime.utcnow()
    
    def to_dict(self, include_plan: bool = True) -> dict:
        """转换为字典（不包含密码）"""
        result = {
            "user_id": self.user_id,
            "email": self.email,
            "username": self.username,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
            # Phase 3 新增字段
            "plan_id": self.plan_id,
            "points_balance": self.points_balance,
            "monthly_usage": self.monthly_usage,
            "subscription_expires_at": self.subscription_expires_at.isoformat() if self.subscription_expires_at else None,
            "last_usage_reset_at": self.last_usage_reset_at.isoformat() if self.last_usage_reset_at else None
        }
        if include_plan and self.plan_id in PLANS_DICT:
            result["plan_name"] = PLANS_DICT[self.plan_id]["name"]
        return result
    
    def get_plan(self) -> dict:
        """获取当前套餐详情"""
        return PLANS_DICT.get(self.plan_id, SUBSCRIPTION_PLANS[0])
    
    def get_monthly_quota(self) -> int:
        """获取每月检测配额"""
        return self.get_plan()["monthly_quota"]
    
    def get_monthly_remaining(self) -> int:
        """获取本月剩余检测次数"""
        return max(0, self.get_monthly_quota() - self.monthly_usage)
    
    def can_detect(self) -> tuple:
        """检查是否可以进行检测 (can_detect, reason)"""
        # 检查每月配额
        if self.monthly_usage >= self.get_monthly_quota():
            return False, "检测次数不足，请升级套餐"
        # 检查积分（至少需要 10 积分）
        if self.points_balance < 10:
            return False, "积分不足，请充值"
        return True, ""
    
    def deduct_usage(self):
        """扣除一次检测次数"""
        self.monthly_usage += 1
    
    def add_points(self, amount: int):
        """增加积分"""
        self.points_balance += amount
    
    def deduct_points(self, amount: int) -> bool:
        """扣除积分，成功返回 True"""
        if self.points_balance >= amount:
            self.points_balance -= amount
            return True
        return False


class GEOVerification:
    """GEO 验证批次数据模型"""
    
    def __init__(
        self,
        verification_id: str,
        user_id: str,
        scenario: str,  # "progress"（进度验证）或 "delivery"（交付验证）
        geo_plan: dict,  # {keywords, platforms, geo_company?}
        geo_claimed_data: list = None,  # 乙方声称的数据
        prismamate_detection_data: list = None,  # PrismaMate 独立检测结果
        differences: list = None,  # 差异列表
        created_at: datetime = None
    ):
        self.verification_id = verification_id
        self.user_id = user_id
        self.scenario = scenario
        self.geo_plan = geo_plan
        self.geo_claimed_data = geo_claimed_data or []
        self.prismamate_detection_data = prismamate_detection_data or []
        self.differences = differences or []
        self.created_at = created_at or datetime.utcnow()
        self.report_id = None  # 关联的报告ID
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "verification_id": self.verification_id,
            "user_id": self.user_id,
            "scenario": self.scenario,
            "geo_plan": self.geo_plan,
            "geo_claimed_data": self.geo_claimed_data,
            "prismamate_detection_data": self.prismamate_detection_data,
            "differences": self.differences,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "report_id": self.report_id
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
        created_at: datetime = None,
        # V3.0 新增字段
        template_id: str = None,
        parent_report_id: str = None,
        report_type: str = "health_check",  # health_check / geo_verification
        brands: List[dict] = None,  # 品牌配置 [{"full_name": "华为", "short_names": ["华为"]}]
        detection_results: List[dict] = None  # 检测结果明细，用于对比
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
        # V3.0 新增
        self.template_id = template_id
        self.parent_report_id = parent_report_id
        self.report_type = report_type
        self.brands = brands or []
        self.detection_results = detection_results or []
    
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
            "created_at": self.created_at.isoformat(),
            # V3.0 新增字段
            "template_id": self.template_id,
            "parent_report_id": self.parent_report_id,
            "report_type": self.report_type,
            "brands": self.brands,
            "detection_results": self.detection_results
        }


class UserStore:
    """用户数据内存存储（Phase 3 扩展：订阅体系）"""
    
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
        # V3.0 新增：体检模板存储: {template_id: HealthCheckTemplate}
        self._templates: Dict[str, HealthCheckTemplate] = {}
        # 模板索引: {user_id: [template_id, ...]} 按用户分组
        self._templates_by_user: Dict[str, List[str]] = {}
        # V3.0 Phase 2 新增：GEO 验证批次存储: {verification_id: GEOVerification}
        self._geo_verifications: Dict[str, GEOVerification] = {}
        # GEO 验证索引: {user_id: [verification_id, ...]} 按用户分组
        self._geo_verifications_by_user: Dict[str, List[str]] = {}
        
        # Phase 3 新增：积分流水存储 {transaction_id: PointsTransaction}
        self._points_transactions: Dict[str, PointsTransaction] = {}
        # 积分流水索引: {user_id: [transaction_id, ...]} 按用户分组
        self._points_transactions_by_user: Dict[str, List[str]] = {}
        
        # Phase 3 新增：支付订单存储 {order_id: PaymentOrder}
        self._payment_orders: Dict[str, PaymentOrder] = {}
        # 支付订单索引: {user_id: [order_id, ...]} 按用户分组
        self._payment_orders_by_user: Dict[str, List[str]] = {}
        
        # Phase 3 新增：管理员账号存储 {username: Admin}
        self._admins: Dict[str, Admin] = {}
        
        # Phase 3 初始化订阅计划（预置数据，内存存储）
        self._subscription_plans = SUBSCRIPTION_PLANS.copy()
        
        # 初始化演示用户和管理员
        self._init_demo_user()
        self._init_admin()
    
    def _init_demo_user(self):
        """初始化演示用户（Phase 3: 默认单棱MINI版，50积分）"""
        demo_user = User(
            user_id="demo-user-001",
            email="demo@prismamate.com",
            username="demo",
            password_hash=hash_password("demo123"),
            created_at=datetime(2026, 1, 1),
            plan_id="plan_mini",
            points_balance=50,
            monthly_usage=0
        )
        self._users[demo_user.email] = demo_user
        self._users_by_username[demo_user.username] = demo_user
        
        # 为演示用户添加初始积分流水
        self._add_points_transaction(
            user_id=demo_user.user_id,
            amount=50,
            balance_after=50,
            type="gift",
            description="新用户注册赠送积分"
        )
    
    def _init_admin(self):
        """初始化超级管理员"""
        admin = Admin(
            admin_id="admin-001",
            username="admin",
            password_hash=hash_password("admin123"),
            role="super_admin",
            created_at=datetime(2026, 1, 1)
        )
        self._admins[admin.username] = admin
    
    # ==================== 管理员操作 ====================
    
    def get_admin_by_username(self, username: str) -> Optional[Admin]:
        """通过用户名获取管理员"""
        return self._admins.get(username)
    
    def get_admin_by_id(self, admin_id: str) -> Optional[Admin]:
        """通过ID获取管理员"""
        for admin in self._admins.values():
            if admin.admin_id == admin_id:
                return admin
        return None
    
    def verify_admin(self, username: str, password: str) -> Optional[Admin]:
        """验证管理员登录"""
        admin = self._admins.get(username)
        if admin and self._verify_password(password, admin.password_hash):
            return admin
        return None
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码（与 auth.py 中的 verify_password 逻辑一致）"""
        from app.core.auth import verify_password
        return verify_password(password, password_hash)
    
    # ==================== 订阅计划操作 ====================
    
    def get_subscription_plans(self) -> List[dict]:
        """获取所有订阅计划"""
        return self._subscription_plans.copy()
    
    def get_plan_by_id(self, plan_id: str) -> Optional[dict]:
        """通过ID获取订阅计划"""
        for plan in self._subscription_plans:
            if plan["id"] == plan_id:
                return plan.copy()
        return None
    
    def update_plan(self, plan_id: str, updates: dict) -> Optional[dict]:
        """更新订阅计划"""
        for i, plan in enumerate(self._subscription_plans):
            if plan["id"] == plan_id:
                self._subscription_plans[i].update(updates)
                return self._subscription_plans[i].copy()
        return None
    
    # ==================== 积分流水操作 ====================
    
    def _add_points_transaction(
        self,
        user_id: str,
        amount: int,
        balance_after: int,
        type: str,
        description: str
    ) -> PointsTransaction:
        """内部方法：添加积分流水记录"""
        transaction = PointsTransaction(
            transaction_id=f"PT-{uuid.uuid4().hex[:12].upper()}",
            user_id=user_id,
            amount=amount,
            balance_after=balance_after,
            type=type,
            description=description
        )
        self._points_transactions[transaction.transaction_id] = transaction
        
        # 更新用户积分流水索引
        if user_id not in self._points_transactions_by_user:
            self._points_transactions_by_user[user_id] = []
        self._points_transactions_by_user[user_id].append(transaction.transaction_id)
        
        return transaction
    
    def add_points_to_user(
        self,
        user_id: str,
        amount: int,
        type: str,
        description: str
    ) -> tuple:
        """
        为用户添加积分
        
        Returns: (success: bool, message: str, transaction: Optional[PointsTransaction])
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return False, "用户不存在", None
        
        user.add_points(amount)
        transaction = self._add_points_transaction(
            user_id=user_id,
            amount=amount,
            balance_after=user.points_balance,
            type=type,
            description=description
        )
        return True, "积分添加成功", transaction
    
    def deduct_points_from_user(
        self,
        user_id: str,
        amount: int,
        type: str,
        description: str
    ) -> tuple:
        """
        从用户扣除积分
        
        Returns: (success: bool, message: str, transaction: Optional[PointsTransaction])
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return False, "用户不存在", None
        
        if not user.deduct_points(amount):
            return False, "积分不足", None
        
        transaction = self._add_points_transaction(
            user_id=user_id,
            amount=-amount,
            balance_after=user.points_balance,
            type=type,
            description=description
        )
        return True, "积分扣除成功", transaction
    
    def get_points_transactions_by_user(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[PointsTransaction]:
        """获取用户的积分流水（按时间倒序）"""
        transaction_ids = self._points_transactions_by_user.get(user_id, [])
        transactions = []
        for tid in transaction_ids:
            transaction = self._points_transactions.get(tid)
            if transaction:
                transactions.append(transaction)
        # 按时间倒序
        transactions.sort(key=lambda t: t.created_at, reverse=True)
        return transactions[:limit]
    
    def get_all_points_transactions(self, limit: int = 100) -> List[PointsTransaction]:
        """获取所有积分流水（管理员用）"""
        transactions = list(self._points_transactions.values())
        transactions.sort(key=lambda t: t.created_at, reverse=True)
        return transactions[:limit]
    
    # ==================== 支付订单操作 ====================
    
    def create_payment_order(
        self,
        user_id: str,
        order_type: str,
        plan_id: str = None,
        points_amount: int = 0,
        amount: float = 0
    ) -> PaymentOrder:
        """创建支付订单"""
        order = PaymentOrder(
            order_id=f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            user_id=user_id,
            order_type=order_type,
            plan_id=plan_id,
            points_amount=points_amount,
            amount=amount,
            status="pending"
        )
        self._payment_orders[order.order_id] = order
        
        # 更新用户订单索引
        if user_id not in self._payment_orders_by_user:
            self._payment_orders_by_user[user_id] = []
        self._payment_orders_by_user[user_id].append(order.order_id)
        
        return order
    
    def get_payment_order(self, order_id: str) -> Optional[PaymentOrder]:
        """获取支付订单"""
        return self._payment_orders.get(order_id)
    
    def update_payment_order_status(
        self,
        order_id: str,
        status: str
    ) -> Optional[PaymentOrder]:
        """更新支付订单状态"""
        order = self._payment_orders.get(order_id)
        if order:
            order.status = status
            if status == "paid":
                order.paid_at = datetime.utcnow()
        return order
    
    def get_payment_orders_by_user(self, user_id: str) -> List[PaymentOrder]:
        """获取用户的支付订单"""
        order_ids = self._payment_orders_by_user.get(user_id, [])
        orders = []
        for oid in order_ids:
            order = self._payment_orders.get(oid)
            if order:
                orders.append(order)
        orders.sort(key=lambda o: o.created_at, reverse=True)
        return orders
    
    def get_all_payment_orders(self, limit: int = 100) -> List[PaymentOrder]:
        """获取所有支付订单（管理员用）"""
        orders = list(self._payment_orders.values())
        orders.sort(key=lambda o: o.created_at, reverse=True)
        return orders[:limit]
    
    # ==================== 用户操作 ====================
    
    def create_user(self, email: str, username: str, password: str) -> Optional[User]:
        """
        创建新用户（Phase 3: 自动分配 plan_mini，赠送 50 积分）
        
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
        
        # 创建用户（Phase 3: 默认单棱MINI版，50积分）
        user = User(
            user_id=f"user-{uuid.uuid4().hex[:12]}",
            email=email,
            username=username,
            password_hash=hash_password(password),
            plan_id="plan_mini",
            points_balance=50,
            monthly_usage=0
        )
        
        self._users[email] = user
        self._users_by_username[username] = user
        
        # 添加初始积分流水记录
        self._add_points_transaction(
            user_id=user.user_id,
            amount=50,
            balance_after=50,
            type="gift",
            description="新用户注册赠送积分"
        )
        
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
    
    def get_all_users(self) -> List[User]:
        """获取所有用户"""
        return list(self._users.values())
    
    def get_user_count(self) -> int:
        """获取用户总数"""
        return len(self._users)
    
    def update_user_plan(self, user_id: str, plan_id: str) -> Optional[User]:
        """更新用户套餐"""
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        
        # 验证套餐是否存在
        if not self.get_plan_by_id(plan_id):
            return None
        
        user.plan_id = plan_id
        return user
    
    def update_user_subscription_expires(
        self,
        user_id: str,
        expires_at: datetime
    ) -> Optional[User]:
        """更新用户订阅到期时间"""
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        
        user.subscription_expires_at = expires_at
        return user
    
    def ban_user(self, user_id: str, is_active: bool) -> Optional[User]:
        """封禁/解封用户"""
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        
        user.is_active = is_active
        return user
    
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
        report_html: str = "",
        # V3.0 新增参数
        template_id: str = None,
        parent_report_id: str = None,
        report_type: str = "health_check",
        brands: List[dict] = None,
        detection_results: List[dict] = None
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
            report_html=report_html,
            # V3.0 新增
            template_id=template_id,
            parent_report_id=parent_report_id,
            report_type=report_type,
            brands=brands,
            detection_results=detection_results
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
    
    def get_reports_by_template(self, template_id: str) -> List[Report]:
        """获取同一模板的所有报告（按创建时间倒序）"""
        reports = [
            report for report in self._reports.values()
            if report.template_id == template_id
        ]
        # 按创建时间倒序
        reports.sort(key=lambda r: r.created_at, reverse=True)
        return reports
    
    def get_latest_report_by_template(self, template_id: str, exclude_report_id: str = None) -> Optional[Report]:
        """获取同一模板的最新报告（排除指定报告ID）"""
        reports = self.get_reports_by_template(template_id)
        if exclude_report_id:
            reports = [r for r in reports if r.report_id != exclude_report_id]
        return reports[0] if reports else None
    
    # ==================== V3.0 体检模板操作 ====================
    
    def create_template(
        self,
        user_id: str,
        name: str,
        brands: List[dict],
        keywords: List[str],
        platforms: List[str]
    ) -> HealthCheckTemplate:
        """
        创建体检模板
        
        Returns:
            HealthCheckTemplate 对象
        """
        template = HealthCheckTemplate(
            template_id=f"TPL-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
            user_id=user_id,
            name=name,
            brands=brands,
            keywords=keywords,
            platforms=platforms
        )
        self._templates[template.template_id] = template
        
        # 更新用户模板索引
        if user_id not in self._templates_by_user:
            self._templates_by_user[user_id] = []
        self._templates_by_user[user_id].append(template.template_id)
        
        return template
    
    def get_template(self, template_id: str) -> Optional[HealthCheckTemplate]:
        """获取模板"""
        return self._templates.get(template_id)
    
    def get_templates_by_user(self, user_id: str) -> List[HealthCheckTemplate]:
        """获取用户的所有模板（按最后使用时间倒序）"""
        template_ids = self._templates_by_user.get(user_id, [])
        templates = []
        for tid in template_ids:
            template = self._templates.get(tid)
            if template:
                templates.append(template)
        # 按最后使用时间倒序，未使用的排在前面
        templates.sort(key=lambda t: t.last_used_at or datetime.min, reverse=True)
        return templates
    
    def update_template(
        self,
        template_id: str,
        name: str = None,
        brands: List[dict] = None,
        keywords: List[str] = None,
        platforms: List[str] = None
    ) -> Optional[HealthCheckTemplate]:
        """更新模板"""
        template = self._templates.get(template_id)
        if not template:
            return None
        
        if name is not None:
            template.name = name
        if brands is not None:
            template.brands = brands
        if keywords is not None:
            template.keywords = keywords
        if platforms is not None:
            template.platforms = platforms
        
        template.updated_at = datetime.utcnow()
        return template
    
    def delete_template(self, template_id: str) -> bool:
        """删除模板"""
        template = self._templates.get(template_id)
        if not template:
            return False
        
        user_id = template.user_id
        del self._templates[template_id]
        
        # 更新用户模板索引
        if user_id in self._templates_by_user:
            self._templates_by_user[user_id] = [
                tid for tid in self._templates_by_user[user_id]
                if tid != template_id
            ]
        
        return True
    
    # ==================== V3.0 Phase 2 GEO 验证操作 ====================
    
    def create_geo_verification(
        self,
        user_id: str,
        scenario: str,
        geo_plan: dict,
        geo_claimed_data: list = None
    ) -> GEOVerification:
        """
        创建 GEO 验证批次
        
        Args:
            user_id: 用户ID
            scenario: 场景 "progress" 或 "delivery"
            geo_plan: GEO 优化方案 {keywords, platforms, geo_company?}
            geo_claimed_data: 乙方声称的数据（可选）
        
        Returns:
            GEOVerification 对象
        """
        # 生成 verification_id: GV-YYYYMMDD-XXXX
        date_str = datetime.utcnow().strftime('%Y%m%d')
        unique_suffix = uuid.uuid4().hex[:4].upper()
        verification_id = f"GV-{date_str}-{unique_suffix}"
        
        verification = GEOVerification(
            verification_id=verification_id,
            user_id=user_id,
            scenario=scenario,
            geo_plan=geo_plan,
            geo_claimed_data=geo_claimed_data or []
        )
        
        self._geo_verifications[verification_id] = verification
        
        # 更新用户验证索引
        if user_id not in self._geo_verifications_by_user:
            self._geo_verifications_by_user[user_id] = []
        self._geo_verifications_by_user[user_id].append(verification_id)
        
        return verification
    
    def get_geo_verification(self, verification_id: str) -> Optional[GEOVerification]:
        """获取 GEO 验证批次"""
        return self._geo_verifications.get(verification_id)
    
    def get_geo_verifications_by_user(self, user_id: str) -> List[GEOVerification]:
        """获取用户的所有 GEO 验证批次（按创建时间倒序）"""
        verification_ids = self._geo_verifications_by_user.get(user_id, [])
        verifications = []
        for vid in verification_ids:
            verification = self._geo_verifications.get(vid)
            if verification:
                verifications.append(verification)
        # 按创建时间倒序
        verifications.sort(key=lambda v: v.created_at, reverse=True)
        return verifications
    
    def update_geo_verification(
        self,
        verification_id: str,
        prismamate_detection_data: list = None,
        differences: list = None,
        report_id: str = None
    ) -> Optional[GEOVerification]:
        """更新 GEO 验证批次（检测完成后）"""
        verification = self._geo_verifications.get(verification_id)
        if not verification:
            return None
        
        if prismamate_detection_data is not None:
            verification.prismamate_detection_data = prismamate_detection_data
        if differences is not None:
            verification.differences = differences
        if report_id is not None:
            verification.report_id = report_id
        
        return verification
    
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
    
    def get_dashboard_stats(self) -> dict:
        """获取仪表盘统计数据（管理员用）"""
        users = self.get_all_users()
        total_users = len(users)
        
        # 付费用户数
        paid_users = [u for u in users if u.plan_id != "plan_mini"]
        paid_count = len(paid_users)
        paid_rate = (paid_count / total_users * 100) if total_users > 0 else 0
        
        # MRR（月度经常性收入）
        mrr = 0
        for user in paid_users:
            plan = self.get_plan_by_id(user.plan_id)
            if plan:
                mrr += plan.get("monthly_price", 0)
        
        # 今日检测次数
        today = datetime.utcnow().date()
        today_tasks = [
            t for t in self._tasks.values()
            if t.created_at.date() == today and t.status == "completed"
        ]
        today_detections = len(today_tasks)
        
        # 总检测次数
        total_detections = len([t for t in self._tasks.values() if t.status == "completed"])
        
        return {
            "total_users": total_users,
            "paid_users": paid_count,
            "paid_rate": round(paid_rate, 1),
            "mrr": mrr,
            "today_detections": today_detections,
            "total_detections": total_detections
        }


# 全局用户存储实例
user_store = UserStore()
