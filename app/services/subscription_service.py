"""
PrismaMate 棱镜 - 订阅与积分服务（Phase 3）

提供订阅检查、积分管理、配额重置等功能
"""

from datetime import datetime
from typing import Optional, Tuple

from app.core.user_store import user_store


class SubscriptionService:
    """订阅与积分服务"""
    
    # 检测消耗积分（每次检测固定消耗）
    DETECTION_POINTS_COST = 10
    
    # 积分充值价格（100积分 = 10元）
    POINTS_PRICE_PER_100 = 10.0
    
    @staticmethod
    def get_user_plan(user_id: str) -> Optional[dict]:
        """
        获取用户当前套餐详情
        
        Returns:
            套餐信息 dict，包含详细权益描述
        """
        user = user_store.get_user_by_id(user_id)
        if not user:
            return None
        
        plan = user.get_plan()
        return {
            **plan,
            "user_plan_id": user.plan_id,
            "points_balance": user.points_balance,
            "monthly_usage": user.monthly_usage,
            "monthly_remaining": user.get_monthly_remaining(),
            "monthly_quota": user.get_monthly_quota(),
            "subscription_expires_at": user.subscription_expires_at.isoformat() if user.subscription_expires_at else None
        }
    
    @staticmethod
    def get_all_plans() -> list:
        """获取所有订阅计划"""
        return user_store.get_subscription_plans()
    
    @staticmethod
    def check_quota(user_id: str) -> Tuple[bool, str]:
        """
        检查本月剩余检测次数
        
        Returns:
            (can_detect: bool, message: str)
        """
        user = user_store.get_user_by_id(user_id)
        if not user:
            return False, "用户不存在"
        
        remaining = user.get_monthly_remaining()
        if remaining <= 0:
            return False, "检测次数不足，请升级套餐"
        
        return True, f"本月剩余 {remaining} 次检测"
    
    @staticmethod
    def check_points(user_id: str, cost: int = None) -> Tuple[bool, str]:
        """
        检查积分是否足够
        
        Args:
            user_id: 用户ID
            cost: 消耗积分数，默认使用 DETECTION_POINTS_COST
        
        Returns:
            (sufficient: bool, message: str)
        """
        cost = cost or SubscriptionService.DETECTION_POINTS_COST
        
        user = user_store.get_user_by_id(user_id)
        if not user:
            return False, "用户不存在"
        
        if user.points_balance < cost:
            return False, "积分不足，请充值"
        
        return True, f"积分充足（当前余额: {user.points_balance}）"
    
    @staticmethod
    def check_detection_permission(user_id: str) -> Tuple[bool, str]:
        """
        综合检查是否可以进行检测（配额 + 积分）
        
        Returns:
            (can_detect: bool, message: str)
        """
        # 检查配额
        can_quota, quota_msg = SubscriptionService.check_quota(user_id)
        if not can_quota:
            return False, quota_msg
        
        # 检查积分
        can_points, points_msg = SubscriptionService.check_points(user_id)
        if not can_points:
            return False, points_msg
        
        return True, "可以开始检测"
    
    @staticmethod
    def deduct_points(
        user_id: str,
        amount: int = None,
        description: str = "品牌检测消耗"
    ) -> Tuple[bool, str]:
        """
        扣除积分并记录流水
        
        Args:
            user_id: 用户ID
            amount: 积分数，默认使用 DETECTION_POINTS_COST
            description: 消耗描述
        
        Returns:
            (success: bool, message: str)
        """
        amount = amount or SubscriptionService.DETECTION_POINTS_COST
        
        success, msg, _ = user_store.deduct_points_from_user(
            user_id=user_id,
            amount=amount,
            type="detection",
            description=description
        )
        
        return success, msg
    
    @staticmethod
    def add_points(
        user_id: str,
        amount: int,
        type: str = "purchase",
        description: str = "积分充值"
    ) -> Tuple[bool, str]:
        """
        增加积分并记录流水
        
        Args:
            user_id: 用户ID
            amount: 积分数
            type: 类型（purchase/admin_adjust/gift/subscription_grant）
            description: 描述
        
        Returns:
            (success: bool, message: str)
        """
        success, msg, _ = user_store.add_points_to_user(
            user_id=user_id,
            amount=amount,
            type=type,
            description=description
        )
        
        return success, msg
    
    @staticmethod
    def deduct_monthly_usage(user_id: str) -> bool:
        """
        扣除一次月度配额
        
        Returns:
            是否成功
        """
        user = user_store.get_user_by_id(user_id)
        if not user:
            return False
        
        user.deduct_usage()
        return True
    
    @staticmethod
    def get_points_history(user_id: str, limit: int = 50) -> list:
        """
        获取用户积分流水
        
        Returns:
            积分流水列表
        """
        transactions = user_store.get_points_transactions_by_user(user_id, limit)
        return [t.to_dict() for t in transactions]
    
    @staticmethod
    def upgrade_plan(
        user_id: str,
        plan_id: str
    ) -> Tuple[bool, str]:
        """
        升级套餐（预留支付回调，直接生效）
        
        Args:
            user_id: 用户ID
            plan_id: 目标套餐ID
        
        Returns:
            (success: bool, message: str)
        """
        user = user_store.get_user_by_id(user_id)
        if not user:
            return False, "用户不存在"
        
        plan = user_store.get_plan_by_id(plan_id)
        if not plan:
            return False, "套餐不存在"
        
        # 更新用户套餐
        user_store.update_user_plan(user_id, plan_id)
        
        # 更新订阅到期时间（默认加1个月）
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(days=30)
        user_store.update_user_subscription_expires(user_id, expires_at)
        
        # 记录积分流水（如果充值赠送）
        if plan["monthly_points"] > 0:
            user_store.add_points_to_user(
                user_id=user_id,
                amount=plan["monthly_points"],
                type="subscription_grant",
                description=f"订阅「{plan['name']}」赠送积分"
            )
        
        return True, f"套餐升级成功，当前套餐：{plan['name']}"
    
    @staticmethod
    def purchase_points(
        user_id: str,
        points_amount: int
    ) -> Tuple[bool, str, Optional[dict]]:
        """
        积分充值（预留支付，直接增加积分模拟）
        
        Args:
            user_id: 用户ID
            points_amount: 充值积分数（必须是100的倍数）
        
        Returns:
            (success: bool, message: str, order: dict or None)
        """
        # 验证数量（必须是100的倍数）
        if points_amount % 100 != 0:
            return False, "充值数量必须是100的倍数", None
        
        # 计算金额
        amount = (points_amount / 100) * SubscriptionService.POINTS_PRICE_PER_100
        
        # 创建订单
        order = user_store.create_payment_order(
            user_id=user_id,
            order_type="points",
            points_amount=points_amount,
            amount=amount
        )
        
        # 模拟支付成功，直接增加积分
        user_store.update_payment_order_status(order.order_id, "paid")
        success, msg, _ = user_store.add_points_to_user(
            user_id=user_id,
            amount=points_amount,
            type="purchase",
            description=f"积分充值 {points_amount}（订单: {order.order_id}）"
        )
        
        return success, msg, order.to_dict()
    
    @staticmethod
    def get_my_subscriptions(user_id: str) -> list:
        """
        获取用户的订阅记录（支付订单）
        
        Returns:
            订单列表
        """
        orders = user_store.get_payment_orders_by_user(user_id)
        return [o.to_dict() for o in orders]


# 全局服务实例
subscription_service = SubscriptionService()
