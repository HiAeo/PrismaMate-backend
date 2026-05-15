"""
PrismaMate 棱镜 - GEO 验证 API

V3.0 Phase 2 功能：甲方验证乙方 GEO 优化效果
"""

import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.user_store import user_store
from app.api.v1.auth import get_current_user
from app.services.geo_comparison_engine import compute_differences
from app.adapters import get_adapter, list_supported_platforms


router = APIRouter()


# ==================== 请求/响应模型 ====================

class GEOPlanRequest(BaseModel):
    """GEO 优化方案请求"""
    keywords: List[str] = Field(..., min_length=1, description="关键词列表")
    platforms: List[str] = Field(..., min_length=1, description="平台列表")
    geo_company: Optional[str] = Field(None, description="GEO 机构名称（可选）")


class ClaimedDataItem(BaseModel):
    """乙方声称的单条数据"""
    brand: str = Field(..., description="品牌名称")
    keyword: str = Field(..., description="关键词")
    platform: str = Field(..., description="平台名称")
    is_mentioned: Optional[bool] = Field(None, description="是否提及")
    mention_position: Optional[int] = Field(None, description="提及位次")
    mention_rate: Optional[float] = Field(None, description="提及率（百分比）")


class UploadVerificationRequest(BaseModel):
    """上传乙方数据请求"""
    scenario: str = Field(..., description="场景: 'progress'（进度验证）或 'delivery'（交付验证）")
    geo_plan: GEOPlanRequest = Field(..., description="GEO 优化方案")
    geo_claimed_data: Optional[List[ClaimedDataItem]] = Field(None, description="乙方声称的数据（交付验证场景）")


class UploadVerificationResponse(BaseModel):
    """上传响应"""
    verification_id: str
    scenario: str
    geo_plan: dict
    created_at: str


class DetectVerificationResponse(BaseModel):
    """执行检测响应"""
    verification_id: str
    status: str  # "detecting", "completed", "partial_failure"
    message: str
    report_id: Optional[str] = None
    differences_summary: Optional[dict] = None


class DifferenceItem(BaseModel):
    """差异项"""
    brand: str
    keyword: str
    platform: str
    field: str
    claimed_value: Optional[float] = None
    detected_value: Optional[float] = None
    verdict: str


class VerificationReportResponse(BaseModel):
    """验证报告响应"""
    verification_id: str
    scenario: str
    geo_plan: dict
    geo_claimed_data: List[dict]
    differences: List[dict]
    summary: dict
    report_id: Optional[str] = None
    created_at: str


class VerificationHistoryItem(BaseModel):
    """验证历史项"""
    verification_id: str
    scenario: str
    geo_plan: dict
    created_at: str
    report_id: Optional[str] = None
    differences_summary: Optional[dict] = None


# ==================== API 接口 ====================

@router.post("/upload", response_model=UploadVerificationResponse)
async def upload_geo_verification(
    request: UploadVerificationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    上传 GEO 验证数据
    
    - **scenario**: 场景类型
      - `progress`: 进度验证（优化进行中）
      - `delivery`: 交付验证（优化已完成，需要上传乙方数据）
    - **geo_plan**: GEO 优化方案配置
    - **geo_claimed_data**: 乙方声称的数据（仅 delivery 场景需要）
    """
    # 验证场景
    if request.scenario not in ["progress", "delivery"]:
        raise HTTPException(status_code=400, detail="scenario 必须是 'progress' 或 'delivery'")
    
    # delivery 场景必须包含 geo_claimed_data
    if request.scenario == "delivery" and not request.geo_claimed_data:
        raise HTTPException(status_code=400, detail="交付验证场景需要提供 geo_claimed_data")
    
    # 转换为 dict
    geo_plan_dict = {
        "keywords": request.geo_plan.keywords,
        "platforms": request.geo_plan.platforms,
        "geo_company": request.geo_plan.geo_company
    }
    
    geo_claimed_data_list = [
        item.model_dump() for item in (request.geo_claimed_data or [])
    ]
    
    # 创建验证批次
    verification = user_store.create_geo_verification(
        user_id=current_user.user_id,
        scenario=request.scenario,
        geo_plan=geo_plan_dict,
        geo_claimed_data=geo_claimed_data_list
    )
    
    return UploadVerificationResponse(
        verification_id=verification.verification_id,
        scenario=verification.scenario,
        geo_plan=verification.geo_plan,
        created_at=verification.created_at.isoformat()
    )


@router.post("/{verification_id}/detect", response_model=DetectVerificationResponse)
async def detect_geo_verification(
    verification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    执行 PrismaMate 独立检测
    
    根据验证批次中的 geo_plan 配置执行检测，完成后自动计算差异
    """
    verification = user_store.get_geo_verification(verification_id)
    
    if not verification:
        raise HTTPException(status_code=404, detail="验证批次不存在")
    
    if verification.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权访问此验证")
    
    geo_plan = verification.geo_plan
    keywords = geo_plan.get("keywords", [])
    platforms = geo_plan.get("platforms", [])
    
    # 获取支持的平台列表
    supported_platforms = list_supported_platforms()
    
    # 执行检测
    detection_results = []
    failed_platforms = []
    
    for platform in platforms:
        # 标准化平台名称
        normalized_platform = platform.lower()
        
        # 检查是否支持
        if normalized_platform not in supported_platforms:
            # 跳过不支持的平台，但不报错
            failed_platforms.append(platform)
            continue
        
        try:
            adapter = get_adapter(normalized_platform)
            if not adapter:
                failed_platforms.append(platform)
                continue
            
            # 循环检测每个关键词
            for keyword in keywords:
                try:
                    # 检测可能是同步或异步方法
                    detect_result = adapter.detect(keyword=keyword)
                    
                    # 如果是协程则 await
                    import asyncio
                    if asyncio.iscoroutine(detect_result):
                        result = await detect_result
                    else:
                        result = detect_result
                    
                    # 转换结果格式
                    if result.get("success"):
                        brand_mentions = result.get("brand_mentions", [])
                        # 提取引用位置
                        positions = []
                        for mention in brand_mentions:
                            pos = mention.get("position_start", 0)
                            if pos > 0:
                                positions.append(pos)
                        
                        # 计算提及率（基于品牌出现次数/总响应长度估算）
                        mention_rate = 0.0
                        if brand_mentions:
                            # 简化计算：提及率 = 品牌提及次数 / 响应长度 * 100
                            total_text = result.get("response_content", "")
                            mention_rate = min(100.0, len(brand_mentions) / max(1, len(total_text) / 100))
                        
                        detection_results.append({
                            "brand": keyword,  # GEO 验证中，关键词本身作为品牌
                            "keyword": keyword,
                            "platform": normalized_platform,
                            "is_mentioned": len(brand_mentions) > 0,
                            "mention_position": min(positions) if positions else None,
                            "mention_rate": round(mention_rate, 1)
                        })
                    else:
                        # 检测失败，记录为空结果
                        detection_results.append({
                            "brand": keyword,
                            "keyword": keyword,
                            "platform": normalized_platform,
                            "is_mentioned": False,
                            "mention_position": None,
                            "mention_rate": 0.0
                        })
                        
                except Exception as e:
                    print(f"[GEO检测] {platform} 关键词 '{keyword}' 检测失败: {e}")
                    # 单个关键词失败不影响其他关键词
                    
        except Exception as e:
            print(f"[GEO检测] {platform} 初始化适配器失败: {e}")
            failed_platforms.append(platform)
    
    # 计算差异（如果有乙方声称数据）
    differences_result = None
    if verification.geo_claimed_data:
        differences_result = compute_differences(
            geo_data=verification.geo_claimed_data,
            prismamate_data=detection_results,
            supported_platforms=supported_platforms
        )
    
    # 创建报告
    report_id = f"RPT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    # 更新验证批次
    user_store.update_geo_verification(
        verification_id=verification_id,
        prismamate_detection_data=detection_results,
        differences=differences_result.get("differences", []) if differences_result else [],
        report_id=report_id
    )
    
    # 生成状态消息
    status = "completed" if not failed_platforms else "partial_failure"
    if failed_platforms:
        message = f"检测完成，部分平台失败: {', '.join(failed_platforms)}"
    else:
        message = "检测完成"
    
    return DetectVerificationResponse(
        verification_id=verification_id,
        status=status,
        message=message,
        report_id=report_id,
        differences_summary=differences_result.get("summary") if differences_result else None
    )


@router.get("/{verification_id}/report", response_model=VerificationReportResponse)
async def get_verification_report(
    verification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取验证报告详情
    """
    verification = user_store.get_geo_verification(verification_id)
    
    if not verification:
        raise HTTPException(status_code=404, detail="验证批次不存在")
    
    if verification.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权访问此验证")
    
    # 计算汇总（如果尚未计算）
    summary = None
    if verification.geo_claimed_data and verification.prismamate_detection_data:
        supported_platforms = list_supported_platforms()
        diff_result = compute_differences(
            geo_data=verification.geo_claimed_data,
            prismamate_data=verification.prismamate_detection_data,
            supported_platforms=supported_platforms
        )
        summary = diff_result.get("summary")
    
    return VerificationReportResponse(
        verification_id=verification.verification_id,
        scenario=verification.scenario,
        geo_plan=verification.geo_plan,
        geo_claimed_data=verification.geo_claimed_data,
        differences=verification.differences,
        summary=summary or _compute_summary_from_differences(verification.differences),
        report_id=verification.report_id,
        created_at=verification.created_at.isoformat()
    )


@router.get("/history", response_model=List[VerificationHistoryItem])
async def list_verification_history(
    current_user: dict = Depends(get_current_user)
):
    """
    获取当前用户的验证历史列表
    """
    verifications = user_store.get_geo_verifications_by_user(current_user.user_id)
    
    result = []
    for v in verifications:
        # 计算差异汇总（如果已检测）
        diff_summary = None
        if v.differences:
            diff_summary = _compute_summary_from_differences(v.differences)
        
        result.append(VerificationHistoryItem(
            verification_id=v.verification_id,
            scenario=v.scenario,
            geo_plan=v.geo_plan,
            created_at=v.created_at.isoformat(),
            report_id=v.report_id,
            differences_summary=diff_summary
        ))
    
    return result


def _compute_summary_from_differences(differences: List[dict]) -> dict:
    """从差异列表计算汇总"""
    if not differences:
        return {"total_items": 0, "consistent": 0, "different": 0, "out_of_coverage": 0}
    
    summary = {"total_items": 0, "consistent": 0, "different": 0, "out_of_coverage": 0}
    
    # 按 (brand, keyword, platform) 分组计数
    item_verdicts = {}
    for diff in differences:
        key = (diff.get("brand"), diff.get("keyword"), diff.get("platform"))
        verdict = diff.get("verdict", "有差异")
        
        if key not in item_verdicts:
            item_verdicts[key] = set()
        item_verdicts[key].add(verdict)
    
    summary["total_items"] = len(item_verdicts)
    
    for verdicts in item_verdicts.values():
        if "超出覆盖范围" in verdicts:
            summary["out_of_coverage"] += 1
        elif "有差异" in verdicts:
            summary["different"] += 1
        else:
            summary["consistent"] += 1
    
    return summary
