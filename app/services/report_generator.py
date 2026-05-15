# report_generator.py
# PDF 报告生成模块
# 使用 WeasyPrint 从 HTML 模板生成 PDF，支持中文字体
#
# 使用方法：
# from app.services.report_generator import ReportGenerator, generate_report
#
# generator = ReportGenerator()
# report = generator.generate(detection_results, brand_mentions)
# generator.save_pdf(report, "output.pdf")

import os
import re
import hashlib
import datetime
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path

# HTML 模板路径
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
FONT_CONFIG = """
@font-face {
    font-family: 'Source Han Sans';
    src: local('Source Han Sans'), local('Noto Sans CJK SC'), local('Microsoft YaHei'), local('SimHei');
    font-weight: normal;
}
"""


@dataclass
class DetectionResult:
    """检测结果数据"""
    platform: str
    keyword: str
    query_time: datetime.datetime
    response_text: str
    response_time: float
    citations: List[Dict] = field(default_factory=list)
    raw_response: Optional[str] = None


@dataclass
class BrandMentionResult:
    """品牌提及结果"""
    brand_name: str
    canonical_name: str
    position: int
    context: str
    sentiment: str = "neutral"


def convert_brand_match(brand_match) -> BrandMentionResult:
    """
    将 BrandMatch 转换为 BrandMentionResult
    
    Args:
        brand_match: 品牌提取器的 BrandMatch 对象
        
    Returns:
        BrandMentionResult 对象
    """
    # BrandMatch 有 brand_name 字段，没有 canonical_name
    # 对于 BrandMatch，brand_name 就是 canonical_name
    return BrandMentionResult(
        brand_name=brand_match.brand_name,
        canonical_name=brand_match.brand_name,  # BrandMatch.brand_name 就是正式名称
        position=brand_match.position_start,
        context=brand_match.context,
        sentiment=brand_match.sentiment
    )


def convert_brand_matches(brand_matches: list) -> List[BrandMentionResult]:
    """
    批量转换 BrandMatch 列表为 BrandMentionResult 列表
    
    Args:
        brand_matches: BrandMatch 对象列表
        
    Returns:
        BrandMentionResult 对象列表
    """
    return [convert_brand_match(m) for m in brand_matches]


@dataclass
class DetectionReport:
    """检测报告数据"""
    report_id: str
    brand_names: List[str]
    keywords: List[str]
    platforms: List[str]
    detection_time: datetime.datetime
    overall_results: Dict[str, Any]
    report_hash: str
    verification_code: str
    brand_mentions: List[BrandMentionResult] = field(default_factory=list)
    citations: List[Dict] = field(default_factory=list)


class ReportGenerator:
    """
    PDF 报告生成器
    
    功能：
    - 从检测结果生成报告数据
    - 使用 WeasyPrint 生成 PDF
    - 计算报告哈希值用于防篡改验证
    """
    
    # 报告编号计数器（每日重置）
    _daily_counter: Dict[str, int] = {}
    
    def __init__(self, template_dir: Optional[str] = None):
        """
        初始化报告生成器
        
        Args:
            template_dir: HTML 模板目录，默认使用内置模板
        """
        self.template_dir = Path(template_dir) if template_dir else TEMPLATE_DIR
        self._ensure_templates()
    
    def _ensure_templates(self):
        """确保模板目录存在"""
        self.template_dir.mkdir(parents=True, exist_ok=True)
        template_file = self.template_dir / "report_template.html"
        if not template_file.exists():
            self._create_default_template()
    
    def _create_default_template(self):
        """创建默认 HTML 模板"""
        template_content = self._get_html_template()
        template_file = self.template_dir / "report_template.html"
        with open(template_file, 'w', encoding='utf-8') as f:
            f.write(template_content)
        print(f"Created default template: {template_file}")
    
    def generate_report_id(self, date: Optional[datetime.datetime] = None) -> str:
        """
        生成报告编号
        
        格式：PM-YYYYMMDD-XXXX
        Args:
            date: 日期，默认当前时间
            
        Returns:
            报告编号字符串
        """
        if date is None:
            date = datetime.datetime.now()
        
        date_str = date.strftime("%Y%m%d")
        
        # 每日计数器
        if date_str not in self._daily_counter:
            self._daily_counter[date_str] = 0
        self._daily_counter[date_str] += 1
        
        return f"PM-{date_str}-{self._daily_counter[date_str]:04d}"
    
    def generate_verification_code(self, report_id: str) -> str:
        """
        生成 12 位验证码
        
        Args:
            report_id: 报告编号
            
        Returns:
            12 位验证码
        """
        hash_input = f"{report_id}{datetime.datetime.now().isoformat()}"
        hash_bytes = hashlib.sha256(hash_input.encode('utf-8')).digest()
        
        # 使用 base62 编码生成可读验证码
        chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'
        code = ''
        for i in range(12):
            code += chars[hash_bytes[i] % len(chars)]
        
        return code
    
    def calculate_report_hash(self, report_data: Dict) -> str:
        """
        计算报告哈希值
        
        注意：只使用存储时可用的字段，确保验证端可以重新计算相同的哈希值
        
        Args:
            report_data: 报告数据字典
            
        Returns:
            SHA-256 哈希值（十六进制）
        """
        import json
        
        def serialize(obj):
            if isinstance(obj, datetime.datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: serialize(v) for k, v in sorted(obj.items())}
            elif isinstance(obj, list):
                return [serialize(item) for item in obj]
            return obj
        
        # 只使用存储时可用的字段（与 user_store.py Report.to_dict() 一致）
        hash_data = {
            "report_id": report_data.get("report_id"),
            "keywords": report_data.get("keywords", []),
            "platforms": report_data.get("platforms", []),
            "brand_mentions": report_data.get("brand_mentions", []),
        }
        
        serialized = json.dumps(serialize(hash_data), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()
    
    def generate(
        self,
        detection_results: List[DetectionResult],
        brand_mentions: List[BrandMentionResult],
        brands: List[str],
        keywords: List[str],
        platforms: List[str]
    ) -> DetectionReport:
        """
        生成检测报告
        
        Args:
            detection_results: 检测结果列表
            brand_mentions: 品牌提及结果列表
            brands: 品牌名列表
            keywords: 关键词列表
            platforms: 平台列表
            
        Returns:
            DetectionReport 对象
        """
        # 生成报告编号
        report_id = self.generate_report_id()
        
        # 生成验证码
        verification_code = self.generate_verification_code(report_id)
        
        # 构建总体结果
        overall_results = self._build_overall_results(detection_results, brand_mentions)
        
        # 收集所有引用
        all_citations = []
        for result in detection_results:
            all_citations.extend(result.citations or [])
        
        # 截断 brand_mentions 的 context 字段（统一哈希计算和存储）
        MAX_CONTEXT_LENGTH = 100
        truncated_brand_mentions = []
        for m in brand_mentions:
            mention_dict = asdict(m)
            if len(mention_dict.get("context", "")) > MAX_CONTEXT_LENGTH:
                mention_dict["context"] = mention_dict["context"][:MAX_CONTEXT_LENGTH] + "..."
            truncated_brand_mentions.append(mention_dict)
        
        # 构建报告数据
        report_data = {
            "report_id": report_id,
            "brand_names": brands,
            "keywords": keywords,
            "platforms": platforms,
            "detection_time": datetime.datetime.now(),
            "overall_results": overall_results,
            "brand_mentions": truncated_brand_mentions,
            "citations": all_citations,
        }
        
        # 计算哈希值
        report_hash = self.calculate_report_hash(report_data)
        
        return DetectionReport(
            report_id=report_id,
            brand_names=brands,
            keywords=keywords,
            platforms=platforms,
            detection_time=datetime.datetime.now(),
            overall_results=overall_results,
            report_hash=report_hash,
            verification_code=verification_code,
            brand_mentions=brand_mentions,
            citations=all_citations
        )
    
    def _build_overall_results(
        self,
        detection_results: List[DetectionResult],
        brand_mentions: List[BrandMentionResult]
    ) -> Dict[str, Any]:
        """构建总体结果统计"""
        total_queries = len(detection_results)
        successful_queries = len([r for r in detection_results if r.response_text])
        avg_response_time = sum(r.response_time for r in detection_results) / total_queries if total_queries > 0 else 0
        
        # 品牌提及统计
        brand_stats = {}
        for mention in brand_mentions:
            if mention.canonical_name not in brand_stats:
                brand_stats[mention.canonical_name] = {
                    "count": 0,
                    "positions": [],
                    "avg_position": 0
                }
            brand_stats[mention.canonical_name]["count"] += 1
            brand_stats[mention.canonical_name]["positions"].append(mention.position)
        
        for brand, stats in brand_stats.items():
            positions = stats["positions"]
            stats["avg_position"] = sum(positions) / len(positions) if positions else 0
            stats["first_position"] = min(positions) if positions else 0
        
        return {
            "total_queries": total_queries,
            "successful_queries": successful_queries,
            "success_rate": successful_queries / total_queries if total_queries > 0 else 0,
            "avg_response_time": avg_response_time,
            "brand_stats": brand_stats,
            "total_mentions": len(brand_mentions),
            "total_citations": sum(len(r.citations or []) for r in detection_results)
        }
    
    def _get_html_template(self) -> str:
        """获取 HTML 报告模板"""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PrismaMate 检测报告</title>
    <style>
        $FONT_CONFIG
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Source Han Sans', 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif;
            font-size: 12pt;
            line-height: 1.6;
            color: #333;
            background: white;
        }
        
        /* 封面 */
        .cover {
            page-break-after: always;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            padding: 60px;
        }
        
        .cover h1 {
            font-size: 48pt;
            font-weight: bold;
            margin-bottom: 30px;
            letter-spacing: 8px;
        }
        
        .cover .subtitle {
            font-size: 24pt;
            margin-bottom: 60px;
            opacity: 0.9;
        }
        
        .cover .meta {
            font-size: 14pt;
            opacity: 0.8;
        }
        
        .cover .meta-item {
            margin: 15px 0;
        }
        
        .cover .report-id {
            font-size: 20pt;
            font-weight: bold;
            margin-top: 40px;
            padding: 15px 40px;
            border: 2px solid white;
            display: inline-block;
        }
        
        /* 内容页面 */
        .content {
            padding: 40px 60px;
            page-break-after: always;
        }
        
        .content:last-child {
            page-break-after: auto;
        }
        
        h2 {
            font-size: 24pt;
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 15px;
            margin-bottom: 30px;
        }
        
        h3 {
            font-size: 16pt;
            color: #333;
            margin: 25px 0 15px 0;
        }
        
        /* 概要卡片 */
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 40px;
        }
        
        .summary-card {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 25px;
            text-align: center;
            border-left: 4px solid #667eea;
        }
        
        .summary-card .number {
            font-size: 36pt;
            font-weight: bold;
            color: #667eea;
        }
        
        .summary-card .label {
            font-size: 12pt;
            color: #666;
            margin-top: 8px;
        }
        
        /* 品牌提及表格 */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        
        th {
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: bold;
        }
        
        td {
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }
        
        tr:nth-child(even) {
            background: #f8f9fa;
        }
        
        .highlight {
            background: #fff3cd;
            padding: 3px 8px;
            border-radius: 4px;
        }
        
        /* 引用来源 */
        .citation-item {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin: 15px 0;
            border-left: 4px solid #48bb78;
        }
        
        .citation-domain {
            font-weight: bold;
            color: #667eea;
        }
        
        .citation-url {
            color: #666;
            font-size: 10pt;
            word-break: break-all;
        }
        
        /* 验证信息 */
        .verification-box {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 30px;
            text-align: center;
            margin-top: 40px;
        }
        
        .verification-box h3 {
            color: #667eea;
            margin-top: 0;
        }
        
        .verification-code {
            font-family: monospace;
            font-size: 24pt;
            letter-spacing: 4px;
            background: #333;
            color: #0f0;
            padding: 15px 30px;
            display: inline-block;
            border-radius: 8px;
            margin: 20px 0;
        }
        
        .hash-value {
            font-family: monospace;
            font-size: 10pt;
            color: #666;
            word-break: break-all;
            background: #eee;
            padding: 10px;
            border-radius: 4px;
        }
        
        /* 页脚 */
        .page-footer {
            position: fixed;
            bottom: 20px;
            left: 0;
            right: 0;
            text-align: center;
            font-size: 10pt;
            color: #999;
            border-top: 1px solid #eee;
            padding-top: 15px;
        }
        
        .page-number:after {
            content: counter(page);
        }
        
        /* 方法说明 */
        .method-list {
            list-style: none;
        }
        
        .method-list li {
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }
        
        .method-list li:before {
            content: "• ";
            color: #667eea;
            font-weight: bold;
        }
        
        /* 响应式打印 */
        @media print {
            .content {
                padding: 20px 30px;
            }
            
            .cover {
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
        }
    </style>
</head>
<body>
    <!-- 封面 -->
    <div class="cover">
        <h1>PrismaMate</h1>
        <div class="subtitle">AI 可见度检测报告</div>
        <div class="meta">
            <div class="meta-item">检测品牌：$BRAND_NAMES$</div>
            <div class="meta-item">检测时间：$DETECTION_TIME$</div>
            <div class="meta-item">检测平台：$PLATFORMS$</div>
        </div>
        <div class="report-id">$REPORT_ID$</div>
    </div>
    
    <!-- 检测概要 -->
    <div class="content">
        <h2>检测概要</h2>
        
        <div class="summary-grid">
            <div class="summary-card">
                <div class="number">$TOTAL_MENTIONS$</div>
                <div class="label">品牌提及次数</div>
            </div>
            <div class="summary-card">
                <div class="number">$BRAND_COUNT$</div>
                <div class="label">检测品牌数</div>
            </div>
            <div class="summary-card">
                <div class="number">$CITATION_COUNT$</div>
                <div class="label">引用来源数</div>
            </div>
            <div class="summary-card">
                <div class="number">$SUCCESS_RATE$%</div>
                <div class="label">检测成功率</div>
            </div>
        </div>
        
        <h3>关键发现</h3>
        <div class="key-findings">
            $KEY_FINDINGS$
        </div>
    </div>
    
    <!-- AI 可见度详情 -->
    <div class="content">
        <h2>AI 可见度详情</h2>
        
        <h3>品牌提及详情</h3>
        $BRAND_TABLE$
    </div>
    
    <!-- 信源分析 -->
    <div class="content">
        <h2>信源分析</h2>
        
        $CITATIONS_LIST$
    </div>
    
    <!-- 检测方法说明 -->
    <div class="content">
        <h2>检测方法说明</h2>
        
        <h3>检测环境</h3>
        <ul class="method-list">
            <li>检测平台：$PLATFORMS$</li>
            <li>API 模式：通过官方 API 接口获取响应</li>
            <li>数据采集时间：$DETECTION_TIME$</li>
        </ul>
        
        <h3>检测流程</h3>
        <ul class="method-list">
            <li>1. 向 AI 平台发送关键词查询</li>
            <li>2. 接收并解析 AI 回答内容</li>
            <li>3. 使用正则表达式提取品牌提及</li>
            <li>4. 提取并分析引用来源</li>
            <li>5. 生成检测报告</li>
        </ul>
        
        <h3>品牌提取规则</h3>
        <ul class="method-list">
            <li>使用精确匹配算法，支持品牌别名</li>
            <li>排除 URL 和引用来源标注中的品牌名</li>
            <li>仅记录每个品牌的首次提及位次</li>
            <li>上下文提取：提及位置前后 50 字符</li>
        </ul>
    </div>
    
    <!-- 验证信息 -->
    <div class="content">
        <h2>验证信息</h2>
        
        <div class="verification-box">
            <h3>报告验证码</h3>
            <div class="verification-code">$VERIFICATION_CODE$</div>
            
            <p>访问 prismamate.com/verify 输入验证码验证报告真伪</p>
            
            <h3 style="margin-top: 30px;">报告哈希值</h3>
            <div class="hash-value">$REPORT_HASH$</div>
            
            <p style="margin-top: 20px; color: #666;">
                本报告由 PrismaMate 棱镜系统自动生成<br>
                报告内容哈希值用于防篡改验证
            </p>
        </div>
    </div>
</body>
</html>"""
    
    def render_html(self, report: DetectionReport) -> str:
        """
        将报告数据渲染为 HTML
        
        Args:
            report: 报告对象
            
        Returns:
            HTML 字符串
        """
        # 读取模板
        template_file = self.template_dir / "report_template.html"
        if template_file.exists():
            with open(template_file, 'r', encoding='utf-8') as f:
                html = f.read()
        else:
            html = self._get_html_template()
        
        # 构建品牌提及表格
        brand_table = self._build_brand_table(report)
        
        # 构建引用列表
        citations_list = self._build_citations_list(report)
        
        # 构建关键发现
        key_findings = self._build_key_findings(report)
        
        # 替换模板变量
        replacements = {
            "$REPORT_ID$": report.report_id,
            "$BRAND_NAMES$": "、".join(report.brand_names),
            "$DETECTION_TIME$": report.detection_time.strftime("%Y年%m月%d日 %H:%M"),
            "$PLATFORMS$": "、".join(report.platforms),
            "$TOTAL_MENTIONS$": str(len(report.brand_mentions)),
            "$BRAND_COUNT$": str(len(report.brand_names)),
            "$CITATION_COUNT$": str(len(report.citations)),
            "$SUCCESS_RATE$": f"{int(report.overall_results.get('success_rate', 0) * 100)}",
            "$BRAND_TABLE$": brand_table,
            "$CITATIONS_LIST$": citations_list,
            "$KEY_FINDINGS$": key_findings,
            "$VERIFICATION_CODE$": report.verification_code,
            "$REPORT_HASH$": report.report_hash,
        }
        
        for key, value in replacements.items():
            html = html.replace(key, str(value))
        
        return html
    
    def _build_brand_table(self, report: DetectionReport) -> str:
        """构建品牌提及表格 HTML"""
        if not report.brand_mentions:
            return "<p>暂无品牌提及数据</p>"
        
        # 按品牌分组
        brand_data = {}
        for mention in report.brand_mentions:
            brand = mention.canonical_name
            if brand not in brand_data:
                brand_data[brand] = []
            brand_data[brand].append(mention)
        
        rows = []
        for brand, mentions in brand_data.items():
            first = mentions[0]
            rows.append(f"""
            <tr>
                <td><strong>{brand}</strong></td>
                <td>{len(mentions)}</td>
                <td>第 {first.position + 1} 位</td>
                <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis;">{first.context[:50]}...</td>
            </tr>
            """)
        
        return f"""
        <table>
            <thead>
                <tr>
                    <th>品牌</th>
                    <th>提及次数</th>
                    <th>首次出现</th>
                    <th>上下文</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
        """
    
    def _build_citations_list(self, report: DetectionReport) -> str:
        """构建引用来源列表 HTML"""
        if not report.citations:
            return "<p>暂无引用来源数据</p>"
        
        items = []
        seen_domains = set()
        
        for citation in report.citations[:10]:  # 最多显示 10 个
            url = citation.get('url', '')
            domain = citation.get('domain', '')
            
            # 去重
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            
            items.append(f"""
            <div class="citation-item">
                <div class="citation-domain">{domain}</div>
                <div class="citation-url">{url}</div>
            </div>
            """)
        
        return "".join(items) if items else "<p>暂无引用来源数据</p>"
    
    def _build_key_findings(self, report: DetectionReport) -> str:
        """构建关键发现 HTML"""
        findings = []
        
        if report.brand_mentions:
            total = len(report.brand_mentions)
            brands = len(set(m.canonical_name for m in report.brand_mentions))
            findings.append(f"在 {total} 次品牌提及中，共检测到 {brands} 个品牌的可见度")
            
            # 找出提及最多的品牌
            brand_counts = {}
            for m in report.brand_mentions:
                brand_counts[m.canonical_name] = brand_counts.get(m.canonical_name, 0) + 1
            
            if brand_counts:
                top_brand = max(brand_counts.items(), key=lambda x: x[1])
                findings.append(f"品牌 <span class='highlight'>{top_brand[0]}</span> 提及次数最多，共 {top_brand[1]} 次")
        else:
            findings.append("未检测到品牌提及，可能需要调整关键词或检测策略")
        
        return "<ul class='method-list'>" + "".join(f"<li>{f}</li>" for f in findings) + "</ul>"
    
    def generate_pdf(self, report: DetectionReport, output_path: str) -> str:
        """
        生成 PDF 文件
        
        Args:
            report: 报告对象
            output_path: 输出文件路径
            
        Returns:
            生成的 PDF 文件路径
        """
        try:
            from weasyprint import HTML, CSS
        except ImportError:
            raise ImportError(
                "请安装 WeasyPrint: pip install weasyprint\n"
                "Windows 用户可能需要额外安装 GTK3: https://github.com/千家智囊/WeasyPrint-Windows"
            )
        
        # 渲染 HTML
        html_content = self.render_html(report)
        
        # 生成 PDF
        html = HTML(string=html_content)
        html.write_pdf(output_path)
        
        return output_path


def generate_report(
    detection_results: List[DetectionResult],
    brand_mentions: Union[List[BrandMentionResult], list],
    brands: List[str],
    keywords: List[str],
    platforms: List[str],
    output_path: Optional[str] = None
) -> tuple:
    """
    快速生成报告的便捷函数
    
    Args:
        detection_results: 检测结果
        brand_mentions: 品牌提及结果（可以是 BrandMentionResult 或 BrandMatch）
        brands: 品牌列表
        keywords: 关键词列表
        platforms: 平台列表
        output_path: PDF 输出路径
        
    Returns:
        (report, pdf_path) 元组
    """
    generator = ReportGenerator()
    
    # 转换 BrandMatch 为 BrandMentionResult（如果需要）
    if brand_mentions and len(brand_mentions) > 0:
        first_item = brand_mentions[0]
        # 检查是否是 BrandMatch 类型（通过是否有 brand_name 属性且没有 canonical_name）
        if hasattr(first_item, 'brand_name') and not hasattr(first_item, 'canonical_name'):
            brand_mentions = convert_brand_matches(brand_mentions)
    
    # 生成报告数据
    report = generator.generate(
        detection_results=detection_results,
        brand_mentions=brand_mentions,
        brands=brands,
        keywords=keywords,
        platforms=platforms
    )
    
    # 如果指定了输出路径，生成 PDF
    pdf_path = None
    if output_path:
        pdf_path = generator.generate_pdf(report, output_path)
    
    return report, pdf_path
