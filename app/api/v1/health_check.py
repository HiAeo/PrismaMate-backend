"""
PrismaMate 棱镜 - 体检模板 API

V3.0 Phase 1 功能：体检模板 CRUD + 使用模板执行检测
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.user_store import user_store, HealthCheckTemplate
from app.api.v1.auth import get_current_user
from app.api.v1.tasks import _run_detection_for_task


router = APIRouter()


# ==================== 请求/响应模型 ====================

class CreateTemplateRequest(BaseModel):
    """创建模板请求"""
    name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    brands: List[dict] = Field(..., description='品牌配置 [{"full_name": "华为", "short_names": ["华为", "Huawei"]}]')
    keywords: List[str] = Field(..., min_length=1, description="关键词列表")
    platforms: List[str] = Field(..., min_length=1, description="平台列表")


class UpdateTemplateRequest(BaseModel):
    """更新模板请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    brands: Optional[List[dict]] = None
    keywords: Optional[List[str]] = None
    platforms: Optional[List[str]] = None


class TemplateResponse(BaseModel):
    """模板响应"""
    template_id: str
    name: str
    brands: List[dict]
    keywords: List[str]
    platforms: List[str]
    created_at: str
    updated_at: str
    last_used_at: Optional[str] = None


class RunTemplateRequest(BaseModel):
    """使用模板执行检测请求"""
    template_id: str = Field(..., description="模板ID")
    # 可选：覆盖模板配置的参数
    keywords: Optional[List[str]] = None
    platforms: Optional[List[str]] = None


# ==================== API 接口 ====================

@router.post("/templates", response_model=TemplateResponse)
async def create_template(
    request: CreateTemplateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    创建体检模板
    
    - **name**: 模板名称
    - **brands**: 品牌配置列表
    - **keywords**: 关键词列表
    - **platforms**: 平台列表
    """
    template = user_store.create_template(
        user_id=current_user.user_id,
        name=request.name,
        brands=request.brands,
        keywords=request.keywords,
        platforms=request.platforms
    )
    
    return TemplateResponse(**template.to_dict())


@router.get("/templates", response_model=List[TemplateResponse])
async def list_templates(
    current_user: dict = Depends(get_current_user)
):
    """
    获取当前用户的所有模板列表
    
    按最后使用时间倒序排列
    """
    templates = user_store.get_templates_by_user(current_user.user_id)
    return [TemplateResponse(**t.to_dict()) for t in templates]


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取单个模板详情
    """
    template = user_store.get_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    if template.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权访问此模板")
    
    return TemplateResponse(**template.to_dict())


@router.put("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    更新模板
    
    所有字段可选，只更新提供的字段
    """
    template = user_store.get_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    if template.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权修改此模板")
    
    updated = user_store.update_template(
        template_id=template_id,
        name=request.name,
        brands=request.brands,
        keywords=request.keywords,
        platforms=request.platforms
    )
    
    return TemplateResponse(**updated.to_dict())


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    删除模板
    """
    template = user_store.get_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    if template.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权删除此模板")
    
    success = user_store.delete_template(template_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")
    
    return {"message": "模板已删除", "template_id": template_id}


@router.post("/templates/{template_id}/run")
async def run_template(
    template_id: str,
    request: Optional[RunTemplateRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    使用模板参数立即执行检测
    
    自动关联上一次同模板报告用于对比
    """
    template = user_store.get_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    if template.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权使用此模板")
    
    # 更新模板最后使用时间
    template.update_last_used()
    
    # 获取覆盖参数（如果有）
    keywords = request.keywords if request and request.keywords else template.keywords
    platforms = request.platforms if request and request.platforms else template.platforms
    
    # 查找上一次同模板报告（用于对比）
    latest_report = user_store.get_latest_report_by_template(template_id)
    parent_report_id = latest_report.report_id if latest_report else None
    
    # 提取品牌名称列表
    brand_names = [b["full_name"] for b in template.brands]
    
    # 创建任务并执行检测
    platform = platforms[0] if platforms else "DeepSeek"
    task = user_store.create_task(
        user_id=current_user.user_id,
        keywords=keywords,
        brands=brand_names,
        platform=platform
    )
    
    # 执行检测并生成报告
    try:
        report_data = await _run_detection_for_task(
            task_id=task.task_id,
            keywords=keywords,
            brands=brand_names,
            platform=platform,
            template_id=template_id,
            parent_report_id=parent_report_id
        )
        
        return {
            "message": "检测完成",
            "template": template.to_dict(),
            "parent_report_id": parent_report_id,
            "task_id": task.task_id,
            "report": report_data
        }
    except HTTPException as e:
        return {
            "message": "检测失败",
            "template": template.to_dict(),
            "parent_report_id": parent_report_id,
            "task_id": task.task_id,
            "error": str(e.detail)
        }
