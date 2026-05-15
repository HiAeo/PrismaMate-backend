"""
PrismaMate 棱镜 - 报告 API 路由

提供报告列表、详情查询、公开验证等功能
"""

import hashlib
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from app.api.v1.auth import get_current_user, get_optional_user
from app.core.user_store import user_store
from app.services.comparison_engine import generate_comparison, get_comparison_summary_text

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 限流机制 ====================

class RateLimiter:
    """简单的内存限流器"""
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict = defaultdict(list)
        self._lock = Lock()
    
    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """
        检查请求是否允许
        
        Returns:
            (是否允许, 剩余请求数)
        """
        now = time.time()
        cutoff = now - self.window_seconds
        
        with self._lock:
            # 清理过期记录
            self._requests[client_id] = [
                t for t in self._requests[client_id] if t > cutoff
            ]
            
            current_count = len(self._requests[client_id])
            
            if current_count >= self.max_requests:
                return False, 0
            
            # 记录请求
            self._requests[client_id].append(now)
            return True, self.max_requests - current_count - 1
    
    def get_retry_after(self, client_id: str) -> int:
        """获取需要等待的秒数"""
        now = time.time()
        cutoff = now - self.window_seconds
        
        with self._lock:
            timestamps = [t for t in self._requests[client_id] if t > cutoff]
            if not timestamps:
                return 0
            oldest = min(timestamps)
            return int(oldest + self.window_seconds - now)


# 验证接口限流器：单 IP 每分钟最多 10 次
verify_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)


def _get_client_ip(request: Request) -> str:
    """获取客户端 IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _compute_report_hash(report: dict) -> str:
    """
    计算报告哈希值（用于验证）
    
    使用与 report_generator.py 的 calculate_report_hash 相同的 JSON 序列化逻辑
    """
    import json
    
    def serialize(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: serialize(v) for k, v in sorted(obj.items())}
        elif isinstance(obj, list):
            return [serialize(item) for item in obj]
        return obj
    
    # 构建与 report_generator.py 中相同的数据结构（只用存储时可用的字段）
    hash_data = {
        "report_id": report["report_id"],
        "keywords": report.get("keywords", []),
        "platforms": report.get("platforms", []),
        "brand_mentions": report.get("brand_mentions", []),
    }
    
    serialized = json.dumps(serialize(hash_data), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


# ==================== API 端点 ====================

@router.get("/verify/{code}")
async def verify_report(
    code: str,
    request: Request
):
    """
    公开验证报告真伪
    
    无需认证，任何人都可以验证
    限流：单 IP 每分钟最多 10 次
    """
    # 限流检查
    client_ip = _get_client_ip(request)
    is_allowed, remaining = verify_rate_limiter.is_allowed(client_ip)
    
    if not is_allowed:
        retry_after = verify_rate_limiter.get_retry_after(client_ip)
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": "验证请求过于频繁，请稍后再试",
                "retry_after": retry_after
            },
            headers={"Retry-After": str(retry_after)}
        )
    
    report = user_store.get_report_by_code(code)
    
    if not report:
        raise HTTPException(
            status_code=404,
            detail={
                "valid": False,
                "is_valid": False,
                "message": "报告未找到或验证码无效",
                "verification_code": code
            }
        )
    
    # 获取报告字典
    report_dict = report.to_dict()
    
    # 计算当前哈希值
    current_hash = _compute_report_hash(report_dict)
    
    # 比对哈希值
    hash_match = current_hash == report.report_hash
    
    # 计算品牌名称列表
    brand_names = []
    if report.brand_mentions:
        for mention in report.brand_mentions:
            if isinstance(mention, dict) and "brand" in mention:
                brand_names.append(mention["brand"])
    
    # 格式化检测时间
    detection_time = report.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # 返回完整验证信息
    return {
        "valid": True,
        "is_valid": hash_match,
        "message": "此报告由 PrismaMate 出具且未被篡改" if hash_match else "此报告可能已被篡改",
        "report_id": report.report_id,
        "verification_code": report.verification_code,
        "brand_names": brand_names,
        "keywords": report.keywords,
        "platforms": report.platforms,
        "detection_time": detection_time,
        "report_hash": report.report_hash,
        "hash_verified": hash_match,
        "rate_limit_remaining": remaining
    }


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    current_user: dict = Depends(get_optional_user)
):
    """
    获取报告详情
    
    公开报告：任何人都可以查看
    用户报告：需要是报告所有者
    """
    report = user_store.get_report(report_id)
    
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    
    # 如果是用户报告，检查权限
    if report.user_id and current_user:
        if report.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="无权访问此报告")
    
    return report.to_dict()


@router.get("/{report_id}/html")
async def get_report_html(
    report_id: str,
    current_user: dict = Depends(get_optional_user)
):
    """
    获取报告 HTML 内容
    
    公开报告：任何人都可以查看
    用户报告：需要是报告所有者
    """
    report = user_store.get_report(report_id)
    
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    
    # 如果是用户报告，检查权限
    if report.user_id and current_user:
        if report.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="无权访问此报告")
    
    if not report.report_html:
        raise HTTPException(status_code=404, detail="报告 HTML 不存在")
    
    return HTMLResponse(content=report.report_html)


@router.get("")
async def list_reports(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    获取当前用户的报告列表
    
    需要认证
    """
    reports = user_store.get_reports_by_user(current_user.user_id)
    
    # 按创建时间倒序
    reports.sort(key=lambda r: r.created_at, reverse=True)
    
    # 分页
    total = len(reports)
    paginated = reports[offset:offset + limit]
    
    return {
        "reports": [report.to_dict() for report in paginated],
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/{report_id}/comparison")
async def get_report_comparison(
    report_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取报告对比数据
    
    返回当前报告与上一次同模板报告的对比结果
    """
    # 获取当前报告
    report = user_store.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    
    # 检查权限
    if report.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权访问此报告")
    
    # 获取父报告
    parent_report_id = report.parent_report_id
    if not parent_report_id:
        raise HTTPException(
            status_code=404,
            detail="此报告没有可对比的历史数据（首次体检报告）"
        )
    
    parent_report = user_store.get_report(parent_report_id)
    if not parent_report:
        raise HTTPException(status_code=404, detail="对比的历史报告不存在")
    
    # 生成对比数据
    comparison = generate_comparison(
        current_report=report.to_dict(),
        parent_report=parent_report.to_dict()
    )
    
    # 添加摘要文本
    comparison["summary_text"] = get_comparison_summary_text(comparison)
    
    # 添加两份报告的基本信息
    comparison["current_report"] = {
        "report_id": report.report_id,
        "created_at": report.created_at.isoformat(),
        "keywords": report.keywords,
        "platforms": report.platforms
    }
    comparison["parent_report"] = {
        "report_id": parent_report.report_id,
        "created_at": parent_report.created_at.isoformat(),
        "keywords": parent_report.keywords,
        "platforms": parent_report.platforms
    }
    
    return comparison
