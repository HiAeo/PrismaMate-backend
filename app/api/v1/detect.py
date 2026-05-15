"""
PrismaMate 棱镜 - 极简检测 API

调用 DeepSeek 适配器 + 品牌提取器 + 报告生成器
支持 JWT 认证（可选），已登录用户的结果关联到用户账户

Phase 3: 集成配额和积分检查
"""

import datetime
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.api.v1.auth import get_current_user, get_optional_user
from app.services.report_generator import (
    ReportGenerator,
    DetectionResult,
    BrandMentionResult,
    convert_brand_matches,
)
from app.services.brand_extractor import create_extractor
from app.services.subscription_service import subscription_service
from app.core.user_store import user_store

logger = logging.getLogger(__name__)

# 尝试导入平台适配器
try:
    from app.adapters import get_adapter, list_supported_platforms, get_platform_info
    ADAPTER_AVAILABLE = True
    SUPPORTED_PLATFORMS = list_supported_platforms()
except ImportError:
    ADAPTER_AVAILABLE = False
    SUPPORTED_PLATFORMS = ["DeepSeek"]

# 尝试导入冷却管理器（延迟初始化）
_cooldown_manager = None


def _get_cooldown_manager():
    """获取冷却管理器（延迟加载）"""
    global _cooldown_manager
    if _cooldown_manager is None:
        try:
            from app.core.cooldown import get_cooldown_manager
            _cooldown_manager = get_cooldown_manager()
        except ImportError:
            pass
    return _cooldown_manager

router = APIRouter()


# ==================== 请求/响应模型 ====================

class DetectionRequest(BaseModel):
    """检测请求"""
    keywords: List[str] = Field(..., description="检测关键词列表", min_items=1, max_items=10)
    brands: List[str] = Field(default_factory=list, description="品牌列表，为空使用默认列表")
    platform: str = Field(default="DeepSeek", description="AI 平台 (DeepSeek/Doubao/Kimi)")


class BrandMentionResponse(BaseModel):
    """品牌提及响应"""
    brand_name: str
    canonical_name: str
    context: str
    sentiment: str


class ReportResponse(BaseModel):
    """报告响应"""
    report_id: str
    verification_code: str
    report_hash: str
    detection_time: str
    total_mentions: int
    brand_mentions: List[BrandMentionResponse]
    total_citations: int
    keywords: List[str]
    platforms: List[str]
    report_html: str  # 完整的 HTML 报告
    user_id: Optional[str] = None  # 如果已登录，包含用户 ID
    task_id: Optional[str] = None  # 如果已登录，包含任务 ID


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: Optional[str] = None


# ==================== API 端点 ====================

@router.post("/detect", response_model=ReportResponse)
async def run_detection(
    request: DetectionRequest,
    current_user: Optional[dict] = Depends(get_optional_user)  # 可选：已登录用户
):
    """
    执行品牌检测并生成报告
    
    流程：
    1. 调用 DeepSeek API 获取 AI 回答
    2. 使用品牌提取器提取品牌提及
    3. 生成报告
    4. 如果已登录，关联到用户账户
    5. 返回报告数据
    """
    if not ADAPTER_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="适配器模块不可用。请确保已安装必要的依赖。"
        )
    
    # 获取适配器
    platform_name = request.platform or "DeepSeek"
    adapter = get_adapter(platform_name)
    
    if adapter is None:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的平台: {platform_name}。支持的平台: {', '.join(SUPPORTED_PLATFORMS)}"
        )
    
    # 检查冷却期
    cooldown_manager = _get_cooldown_manager()
    if cooldown_manager and cooldown_manager.is_in_cooldown(platform_name):
        remaining = cooldown_manager.get_cooldown_remaining(platform_name)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "platform_in_cooldown",
                "message": f"平台 {platform_name} 当前处于冷却期，请稍后再试",
                "platform": platform_name,
                "cooldown_remaining_seconds": int(remaining),
                "retry_after": int(remaining)
            }
        )
    
    # Phase 3: 如果已登录，检查配额和积分
    if current_user:
        can_detect, reason = subscription_service.check_detection_permission(current_user.user_id)
        if not can_detect:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "quota_or_points_insufficient",
                    "message": reason,
                    "current_plan": current_user.plan_id,
                    "points_balance": current_user.points_balance,
                    "monthly_remaining": current_user.get_monthly_remaining()
                }
            )
    
    # 如果已登录，先创建任务
    task_id = None
    if current_user:
        task = user_store.create_task(
            user_id=current_user.user_id,
            keywords=request.keywords,
            brands=request.brands,
            platform=request.platform
        )
        task_id = task.task_id
        user_store.update_task(task_id, status="running")
    
    try:
        # 1. 使用动态获取的适配器（已在上面获取）
        # 适配器通过 get_adapter() 获取
        
        # 使用传入的品牌列表或默认列表
        brands = request.brands if request.brands else None
        extractor = create_extractor(brands=brands)
        
        # 2. 收集所有检测结果
        all_brand_mentions = []
        all_citations = []
        detection_results = []
        
        for keyword in request.keywords:
            # 调用 DeepSeek API
            try:
                result = adapter.detect(keyword)
            except Exception as e:
                import traceback
                logger.error(f"adapter.detect() 异常: {e}\n{traceback.format_exc()}")
                raise
            
            if not result["success"]:
                # 记录失败
                if cooldown_manager:
                    cooldown_manager.record_failure(platform_name)
                
                # 返回 422 结构化错误（非 5xx，避免前端显示 Bad Gateway）
                error_msg = result.get('error', '未知错误')
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": f"{platform_name} 调用失败",
                        "message": error_msg,
                        "platform": platform_name,
                        "status_code": result.get("status_code")
                    }
                )
            
            # 记录成功
            if cooldown_manager:
                cooldown_manager.record_success(platform_name)
            
            # 使用品牌提取器提取提及
            mentions = extractor.extract(result["response_content"])
            converted_mentions = convert_brand_matches(mentions)
            all_brand_mentions.extend(converted_mentions)
            
            # 收集引用
            all_citations.extend(result.get("citations", []))
            
            # 保存检测结果
            detection_results.append(DetectionResult(
                platform=result["platform"],
                keyword=result["keyword"],
                query_time=datetime.datetime.now(),
                response_text=result["response_content"],
                response_time=result.get("elapsed", 0),
                citations=result.get("citations", []),
                raw_response=result.get("response_text")
            ))
        
        # 3. 生成报告
        report_generator = ReportGenerator()
        report = report_generator.generate(
            detection_results=detection_results,
            brand_mentions=all_brand_mentions,
            brands=request.brands if request.brands else extractor.get_brand_names(),
            keywords=request.keywords,
            platforms=[request.platform]
        )
        
        # 4. 生成 HTML
        report_html = report_generator.render_html(report)
        
        # 5. 如果已登录，保存报告到用户账户
        user_id = None
        if current_user:
            user_id = current_user.user_id
            
            # Phase 3: 扣除配额和积分
            subscription_service.deduct_monthly_usage(user_id)
            subscription_service.deduct_points(
                user_id=user_id,
                description=f"品牌检测消耗（关键词: {request.keywords[0]}...）"
            )
            
            user_store.create_report(
                report_id=report.report_id,
                verification_code=report.verification_code,
                report_hash=report.report_hash,
                user_id=user_id,
                task_id=task_id,
                keywords=request.keywords,
                platforms=[request.platform],
                total_mentions=len(all_brand_mentions),
                brand_mentions=[
                    {
                        "brand_name": m.brand_name,
                        "canonical_name": m.canonical_name,
                        "position": m.position,
                        "context": m.context[:100] + "..." if len(m.context) > 100 else m.context,
                        "sentiment": m.sentiment
                    }
                    for m in all_brand_mentions
                ],
                total_citations=len(all_citations),
                report_html=report_html
            )
            # 更新任务状态
            user_store.update_task(task_id, status="completed", report_id=report.report_id)
        
        # 6. 构建响应
        return ReportResponse(
            report_id=report.report_id,
            verification_code=report.verification_code,
            report_hash=report.report_hash,
            detection_time=report.detection_time.isoformat(),
            total_mentions=len(all_brand_mentions),
            brand_mentions=[
                BrandMentionResponse(
                    brand_name=m.brand_name,
                    canonical_name=m.canonical_name,
                    context=m.context,
                    sentiment=m.sentiment
                )
                for m in all_brand_mentions
            ],
            total_citations=len(all_citations),
            keywords=request.keywords,
            platforms=[request.platform],
            report_html=report_html,
            user_id=user_id,
            task_id=task_id
        )
        
    except HTTPException:
        # 更新任务状态为失败
        if current_user and task_id:
            user_store.update_task(task_id, status="failed", error_message="检测过程出错")
        raise
    except Exception as e:
        # 更新任务状态为失败
        if current_user and task_id:
            user_store.update_task(task_id, status="failed", error_message=str(e))
        # 返回详细错误信息
        import traceback
        error_detail = {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/brands")
async def get_default_brands():
    """获取默认品牌列表"""
    extractor = create_extractor()
    return {
        "brands": extractor.get_brand_names()
    }


@router.get("/health")
async def health_check():
    """健康检查"""
    # 获取冷却状态
    cooldown_manager = _get_cooldown_manager()
    platforms_status = []
    if cooldown_manager:
        try:
            platforms_status = cooldown_manager.get_all_platforms_status()
        except Exception:
            pass
    
    return {
        "status": "healthy",
        "adapter_available": ADAPTER_AVAILABLE,
        "supported_platforms": SUPPORTED_PLATFORMS,
        "auth_enabled": True,
        "mvp_mode": True,
        "platforms_status": platforms_status,
        "cooldown_enabled": cooldown_manager is not None
    }


@router.get("/platforms")
async def list_platforms():
    """列出支持的平台"""
    if ADAPTER_AVAILABLE:
        try:
            from app.adapters import get_platform_info
            return {
                "platforms": get_platform_info()
            }
        except ImportError:
            pass
    
    return {
        "platforms": {
            "DeepSeek": {"name": "DeepSeek", "display_name": "DeepSeek", "mode": "api"},
            "Doubao": {"name": "Doubao", "display_name": "豆包", "mode": "browser"},
            "Kimi": {"name": "Kimi", "display_name": "Kimi", "mode": "api"}
        }
    }
