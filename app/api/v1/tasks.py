"""
PrismaMate 棱镜 - 任务 API 路由

提供检测任务创建、历史查询等功能
"""

import datetime
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.v1.auth import get_current_user
from app.core.user_store import user_store
from app.services.report_generator import ReportGenerator, DetectionResult, convert_brand_matches
from app.services.brand_extractor import create_extractor

logger = logging.getLogger(__name__)

# 尝试导入平台适配器
try:
    from app.adapters import get_adapter, list_supported_platforms
    ADAPTER_AVAILABLE = True
except ImportError:
    ADAPTER_AVAILABLE = False
    logger.warning("平台适配器不可用")

router = APIRouter()


# ==================== 请求/响应模型 ====================

class BrandInfo(BaseModel):
    """品牌信息"""
    full_name: str
    short_names: List[str] = []


class CreateTaskRequest(BaseModel):
    """创建任务请求"""
    brands: List[BrandInfo]
    keywords: List[str]
    platforms: List[str]
    competitors: Optional[List[BrandInfo]] = None
    task_type: str = "single"


# ==================== API 端点 ====================

async def _run_detection_for_task(
    task_id: str,
    keywords: List[str],
    brands: List[str],
    platform: str
) -> dict:
    """
    执行检测任务（内部函数）
    
    返回报告数据
    """
    if not ADAPTER_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="平台适配器不可用，请检查依赖安装"
        )
    
    # 获取适配器
    adapter = get_adapter(platform)
    if adapter is None:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的平台: {platform}"
        )
    
    # 更新任务状态为 running
    user_store.update_task(task_id, status="running")
    
    try:
        # 创建品牌提取器
        extractor = create_extractor(brands=brands if brands else None)
        
        # 收集所有检测结果
        all_brand_mentions = []
        all_citations = []
        detection_results = []
        
        for keyword in keywords:
            # 调用平台 API
            result = adapter.detect(keyword)
            
            if not result["success"]:
                raise HTTPException(
                    status_code=502,
                    detail=f"{platform} 调用失败: {result.get('error', '未知错误')}"
                )
            
            # 提取品牌提及
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
                citations=result.get("citations", [])
            ))
        
        # 生成报告
        report_generator = ReportGenerator()
        report = report_generator.generate(
            detection_results=detection_results,
            brand_mentions=all_brand_mentions,
            brands=brands if brands else extractor.get_brand_names(),
            keywords=keywords,
            platforms=[platform]
        )
        
        # 生成 HTML
        report_html = report_generator.render_html(report)
        
        # 保存报告
        user_store.create_report(
            report_id=report.report_id,
            verification_code=report.verification_code,
            report_hash=report.report_hash,
            user_id=user_store.get_task(task_id).user_id,
            task_id=task_id,
            keywords=keywords,
            platforms=[platform],
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
        
        # 更新任务状态为 completed
        user_store.update_task(task_id, status="completed", report_id=report.report_id)
        
        return {
            "report_id": report.report_id,
            "verification_code": report.verification_code,
            "report_hash": report.report_hash,
            "total_mentions": len(all_brand_mentions),
            "total_citations": len(all_citations),
            "status": "completed"
        }
        
    except HTTPException:
        user_store.update_task(task_id, status="failed", error_message="检测过程出错")
        raise
    except Exception as e:
        logger.error(f"检测失败: {e}")
        user_store.update_task(task_id, status="failed", error_message=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_task(
    request: CreateTaskRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    创建并执行检测任务
    
    需要认证
    
    Args:
        brands: 品牌列表
        keywords: 关键词列表
        platforms: AI 平台列表
    
    Returns:
        任务信息和报告数据
    """
    if not request.keywords:
        raise HTTPException(status_code=400, detail="关键词不能为空")
    
    if len(request.keywords) > 10:
        raise HTTPException(status_code=400, detail="关键词数量不能超过 10 个")
    
    # 提取品牌名称列表
    brand_names = [b.full_name for b in request.brands]
    
    # 创建任务
    platform = request.platforms[0] if request.platforms else "DeepSeek"
    task = user_store.create_task(
        user_id=current_user.user_id,
        keywords=request.keywords,
        brands=brand_names,
        platform=platform
    )
    
    # 执行检测并生成报告
    try:
        report_data = await _run_detection_for_task(
            task_id=task.task_id,
            keywords=request.keywords,
            brands=brand_names,
            platform=platform
        )
        
        return {
            "task_id": task.task_id,
            "status": "completed",
            "keywords": task.keywords,
            "brands": task.brands,
            "platform": task.platform,
            "created_at": task.created_at.isoformat(),
            "report": report_data
        }
    except HTTPException as e:
        # 检测失败时仍返回任务信息
        return {
            "task_id": task.task_id,
            "status": "failed",
            "keywords": task.keywords,
            "brands": task.brands,
            "platform": task.platform,
            "created_at": task.created_at.isoformat(),
            "error": e.detail
        }


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取任务详情
    
    需要认证，只能查看自己的任务
    """
    task = user_store.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权访问此任务")
    
    return task.to_dict()


@router.get("/{task_id}/status")
async def get_task_status(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取任务状态
    
    需要认证
    """
    task = user_store.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权访问此任务")
    
    return {
        "task_id": task.task_id,
        "status": task.status,
        "report_id": task.report_id,
        "error_message": task.error_message
    }


@router.get("/{task_id}/results")
async def get_task_results(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取任务检测结果（报告）
    
    需要认证
    """
    task = user_store.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权访问此任务")
    
    if task.status != "completed":
        return {
            "task_id": task.task_id,
            "status": task.status,
            "report_id": None,
            "message": "任务尚未完成"
        }
    
    if task.report_id:
        report = user_store.get_report(task.report_id)
        if report:
            return report.to_dict()
    
    return {
        "task_id": task.task_id,
        "status": task.status,
        "report_id": None,
        "message": "报告未找到"
    }


@router.get("")
async def list_tasks(
    current_user: dict = Depends(get_current_user)
):
    """
    获取任务列表
    
    需要认证
    """
    tasks = user_store.get_tasks_by_user(current_user.user_id)
    
    # 按创建时间倒序
    tasks.sort(key=lambda t: t.created_at, reverse=True)
    
    return {
        "tasks": [task.to_dict() for task in tasks],
        "total": len(tasks)
    }
