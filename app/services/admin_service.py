"""
PrismaMate 棱镜 - 管理员服务（Phase 3）

提供超级管理员后台的数据查询和用户管理功能
"""

from datetime import datetime
from typing import List, Optional, Tuple

from app.core.user_store import user_store, PLANS_DICT


class AdminService:
    """超级管理员服务"""
    
    @staticmethod
    def admin_login(username: str, password: str) -> Tuple[bool, str, Optional[dict]]:
        """
        管理员登录验证
        
        Args:
            username: 管理员用户名
            password: 密码
        
        Returns:
            (success: bool, message: str, admin: dict or None)
        """
        admin = user_store.verify_admin(username, password)
        if not admin:
            return False, "用户名或密码错误", None
        
        return True, "登录成功", admin.to_dict()
    
    @staticmethod
    def verify_admin_role(admin_id: str) -> bool:
        """
        验证管理员角色
        
        Args:
            admin_id: 管理员ID
        
        Returns:
            是否是有效管理员
        """
        admin = user_store.get_admin_by_id(admin_id)
        return admin is not None and admin.role in ["super_admin", "admin"]
    
    @staticmethod
    def get_dashboard_stats() -> dict:
        """
        获取仪表盘统计数据
        
        Returns:
            统计数据字典
        """
        stats = user_store.get_dashboard_stats()
        
        # 获取今日新增用户
        today = datetime.utcnow().date()
        all_users = user_store.get_all_users()
        today_new_users = len([
            u for u in all_users
            if u.created_at.date() == today
        ])
        
        # 获取套餐分布
        plan_distribution = {}
        for plan in PLANS_DICT.keys():
            plan_distribution[plan] = {
                "name": PLANS_DICT[plan]["name"],
                "count": len([u for u in all_users if u.plan_id == plan])
            }
        
        # 获取活跃用户（今日有操作）
        today_tasks = [
            t for t in user_store._tasks.values()
            if t.created_at.date() == today
        ]
        active_user_ids = set(t.user_id for t in today_tasks)
        
        return {
            **stats,
            "today_new_users": today_new_users,
            "active_users": len(active_user_ids),
            "plan_distribution": plan_distribution
        }
    
    @staticmethod
    def get_all_users(
        search: str = None,
        plan_id: str = None,
        is_active: bool = None,
        page: int = 1,
        page_size: int = 20
    ) -> dict:
        """
        获取用户列表（支持搜索、筛选、分页）
        
        Args:
            search: 搜索关键词（邮箱/用户名）
            plan_id: 筛选套餐
            is_active: 筛选状态（None表示全部）
            page: 页码
            page_size: 每页数量
        
        Returns:
            { users: [], total: int, page: int, page_size: int }
        """
        users = user_store.get_all_users()
        
        # 搜索过滤
        if search:
            search = search.lower()
            users = [
                u for u in users
                if search in u.email.lower() or search in u.username.lower()
            ]
        
        # 套餐筛选
        if plan_id:
            users = [u for u in users if u.plan_id == plan_id]
        
        # 状态筛选
        if is_active is not None:
            users = [u for u in users if u.is_active == is_active]
        
        # 按创建时间倒序
        users.sort(key=lambda u: u.created_at, reverse=True)
        
        # 分页
        total = len(users)
        start = (page - 1) * page_size
        end = start + page_size
        page_users = users[start:end]
        
        # 转换为字典
        user_list = []
        for u in page_users:
            plan = u.get_plan()
            user_list.append({
                **u.to_dict(),
                "plan_name": plan["name"],
                "monthly_remaining": u.get_monthly_remaining()
            })
        
        return {
            "users": user_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    
    @staticmethod
    def get_user_detail(user_id: str) -> Optional[dict]:
        """
        获取用户详情
        
        Returns:
            用户详情 dict
        """
        user = user_store.get_user_by_id(user_id)
        if not user:
            return None
        
        plan = user.get_plan()
        stats = user_store.get_user_stats(user_id)
        
        # 获取积分流水
        transactions = user_store.get_points_transactions_by_user(user_id, 20)
        transaction_list = [t.to_dict() for t in transactions]
        
        # 获取支付订单
        orders = user_store.get_payment_orders_by_user(user_id)
        order_list = [o.to_dict() for o in orders]
        
        return {
            **user.to_dict(),
            "plan_name": plan["name"],
            "plan": plan,
            "stats": stats,
            "transactions": transaction_list,
            "orders": order_list
        }
    
    @staticmethod
    def adjust_user_points(
        admin_id: str,
        target_user_id: str,
        amount: int,
        reason: str
    ) -> Tuple[bool, str]:
        """
        管理员调整用户积分
        
        Args:
            admin_id: 管理员ID
            target_user_id: 目标用户ID
            amount: 调整数量（正数增加，负数减少）
            reason: 调整原因
        
        Returns:
            (success: bool, message: str)
        """
        # 验证管理员权限
        if not AdminService.verify_admin_role(admin_id):
            return False, "无权限执行此操作"
        
        # 获取管理员信息
        admin = user_store.get_admin_by_id(admin_id)
        
        # 验证目标用户
        user = user_store.get_user_by_id(target_user_id)
        if not user:
            return False, "目标用户不存在"
        
        # 执行积分调整
        if amount > 0:
            success, msg, _ = user_store.add_points_to_user(
                user_id=target_user_id,
                amount=amount,
                type="admin_adjust",
                description=f"管理员「{admin.username}」调整：{reason}"
            )
        else:
            success, msg, _ = user_store.deduct_points_from_user(
                user_id=target_user_id,
                amount=abs(amount),
                type="admin_adjust",
                description=f"管理员「{admin.username}」调整：{reason}"
            )
        
        return success, msg
    
    @staticmethod
    def adjust_user_plan(
        admin_id: str,
        target_user_id: str,
        plan_id: str
    ) -> Tuple[bool, str]:
        """
        管理员调整用户套餐
        
        Args:
            admin_id: 管理员ID
            target_user_id: 目标用户ID
            plan_id: 目标套餐ID
        
        Returns:
            (success: bool, message: str)
        """
        # 验证管理员权限
        if not AdminService.verify_admin_role(admin_id):
            return False, "无权限执行此操作"
        
        # 获取管理员信息
        admin = user_store.get_admin_by_id(admin_id)
        
        # 验证目标用户
        user = user_store.get_user_by_id(target_user_id)
        if not user:
            return False, "目标用户不存在"
        
        # 验证套餐
        plan = user_store.get_plan_by_id(plan_id)
        if not plan:
            return False, "目标套餐不存在"
        
        # 更新套餐
        user_store.update_user_plan(target_user_id, plan_id)
        
        # 记录积分流水
        user_store.add_points_to_user(
            user_id=target_user_id,
            amount=plan["monthly_points"],
            type="subscription_grant",
            description=f"管理员「{admin.username}」手动开通：{plan['name']}"
        )
        
        return True, f"套餐已调整为：{plan['name']}"
    
    @staticmethod
    def toggle_user_ban(
        admin_id: str,
        target_user_id: str,
        ban: bool
    ) -> Tuple[bool, str]:
        """
        管理员封禁/解封用户
        
        Args:
            admin_id: 管理员ID
            target_user_id: 目标用户ID
            ban: True=封禁，False=解封
        
        Returns:
            (success: bool, message: str)
        """
        # 验证管理员权限
        if not AdminService.verify_admin_role(admin_id):
            return False, "无权限执行此操作"
        
        # 验证目标用户
        user = user_store.get_user_by_id(target_user_id)
        if not user:
            return False, "目标用户不存在"
        
        # 防止封禁管理员自己
        if user.user_id == admin_id:
            return False, "不能封禁自己的账号"
        
        # 更新状态
        user_store.ban_user(target_user_id, not ban)
        
        action = "封禁" if ban else "解封"
        return True, f"用户已{action}"
    
    @staticmethod
    def get_all_subscriptions(
        page: int = 1,
        page_size: int = 20
    ) -> dict:
        """
        获取所有订阅记录
        
        Returns:
            { orders: [], total: int, page: int, page_size: int }
        """
        orders = user_store.get_all_payment_orders()
        total = len(orders)
        
        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        page_orders = orders[start:end]
        
        # 填充用户信息
        order_list = []
        for o in page_orders:
            order_dict = o.to_dict()
            user = user_store.get_user_by_id(o.user_id)
            if user:
                order_dict["user_email"] = user.email
                order_dict["username"] = user.username
            order_list.append(order_dict)
        
        return {
            "orders": order_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    
    @staticmethod
    def get_all_points_transactions(
        page: int = 1,
        page_size: int = 20
    ) -> dict:
        """
        获取所有积分流水
        
        Returns:
            { transactions: [], total: int, page: int, page_size: int }
        """
        transactions = user_store.get_all_points_transactions()
        total = len(transactions)
        
        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        page_transactions = transactions[start:end]
        
        # 填充用户信息
        transaction_list = []
        for t in page_transactions:
            trans_dict = t.to_dict()
            user = user_store.get_user_by_id(t.user_id)
            if user:
                trans_dict["user_email"] = user.email
                trans_dict["username"] = user.username
            transaction_list.append(trans_dict)
        
        return {
            "transactions": transaction_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    
    @staticmethod
    def get_plans() -> list:
        """
        获取所有套餐配置
        
        Returns:
            套餐列表
        """
        return user_store.get_subscription_plans()
    
    @staticmethod
    def update_plan(
        admin_id: str,
        plan_id: str,
        updates: dict
    ) -> Tuple[bool, str]:
        """
        更新套餐配置
        
        Args:
            admin_id: 管理员ID
            plan_id: 套餐ID
            updates: 更新字段
        
        Returns:
            (success: bool, message: str)
        """
        # 验证管理员权限
        if not AdminService.verify_admin_role(admin_id):
            return False, "无权限执行此操作"
        
        # 不允许修改套餐ID和名称
        if "id" in updates:
            del updates["id"]
        if "name" in updates:
            del updates["name"]
        
        # 更新套餐
        plan = user_store.update_plan(plan_id, updates)
        if not plan:
            return False, "套餐不存在"
        
        return True, "套餐配置已更新"


# 全局服务实例
admin_service = AdminService()
