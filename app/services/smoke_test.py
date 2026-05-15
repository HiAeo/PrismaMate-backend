"""
PrismaMate 棱镜 - 冒烟测试服务

按架构文档 1.5 节实现：
- 使用后台线程模拟定时任务（每周执行）
- 测试内容：用固定关键词执行一次搜索
- 结果记录到内存表
- 连续 2 周失败触发告警（打印到日志）
- 冒烟测试不消耗用户检测额度
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SmokeTestResult:
    """冒烟测试结果"""
    platform: str
    timestamp: datetime
    success: bool
    response_time: float  # 秒
    error_message: str = ""
    response_preview: str = ""  # 响应内容预览（最多 200 字）

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
            "response_time": self.response_time,
            "error_message": self.error_message,
            "response_preview": self.response_preview
        }


class SmokeTestService:
    """
    冒烟测试服务（单例）
    
    MVP 阶段使用后台线程模拟 Celery Beat 定时任务
    
    Celery 启动命令（后续实现）：
    # 启动 Worker:
    celery -A app.celery_app worker --loglevel=info
    
    # 启动 Beat（定时任务调度器）:
    celery -A app.celery_app beat --loglevel=info
    """

    _instance: Optional["SmokeTestService"] = None
    _lock = threading.Lock()

    # 冒烟测试固定关键词
    SMOKE_TEST_KEYWORD = "你好，请介绍一下你自己"

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, interval_seconds: int = 604800):  # 默认 7 天
        # 防止重复初始化
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        
        # 测试间隔（秒），默认 7 天
        self.interval_seconds = interval_seconds
        
        # 冒烟测试结果记录: {platform: [SmokeTestResult, ...]}
        self._test_results: Dict[str, List[SmokeTestResult]] = {}
        
        # 每平台保留的测试记录数
        self._max_results_per_platform = 52  # 约一年
        
        # 连续失败计数: {platform: consecutive_failures}
        self._consecutive_failures: Dict[str, int] = {}
        
        # 上次测试时间: {platform: timestamp}
        self._last_test_time: Dict[str, datetime] = {}
        
        # 后台线程
        self._test_thread: Optional[threading.Thread] = None
        self._stop_test = threading.Event()
        self._next_run_time: Optional[datetime] = None
        
        # 启动后台测试线程
        self._start_test_thread()
        
        logger.info(f"冒烟测试服务初始化完成: 测试间隔={self.interval_seconds}秒")

    def _start_test_thread(self):
        """启动后台测试线程"""
        if self._test_thread is None or not self._test_thread.is_alive():
            self._stop_test.clear()
            self._test_thread = threading.Thread(
                target=self._test_loop,
                daemon=True,
                name="smoke-test"
            )
            self._test_thread.start()
            self._next_run_time = datetime.utcnow()
            logger.info(f"冒烟测试线程已启动，下次运行时间: {self._next_run_time.isoformat()}")

    def _test_loop(self):
        """后台测试循环"""
        while not self._stop_test.is_set():
            try:
                # 执行所有平台的冒烟测试
                self.run_smoke_test()
                
                # 计算下次运行时间
                self._next_run_time = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"冒烟测试循环异常: {e}")
            
            # 等待下一次测试（使用较短间隔以便快速响应停止信号）
            for _ in range(min(self.interval_seconds, 3600)):  # 最多等待 1 小时
                if self._stop_test.is_set():
                    break
                time.sleep(1)

    def run_smoke_test(self) -> Dict[str, SmokeTestResult]:
        """
        执行所有平台的冒烟测试
        
        Returns:
            {platform: SmokeTestResult}
        """
        results = {}
        
        try:
            from app.adapters import list_supported_platforms
            
            platforms = list_supported_platforms()
            logger.info(f"开始冒烟测试，平台列表: {platforms}")
            
            for platform in platforms:
                result = self._test_platform(platform)
                results[platform] = result
                
                # 记录连续失败
                if result.success:
                    self._consecutive_failures[platform] = 0
                else:
                    self._consecutive_failures[platform] = self._consecutive_failures.get(platform, 0) + 1
                    consecutive = self._consecutive_failures[platform]
                    
                    # 连续 2 周失败触发告警
                    if consecutive >= 2:
                        self._send_alert(platform, result)
            
            self._next_run_time = datetime.fromtimestamp(time.time() + self.interval_seconds)
            logger.info(f"冒烟测试完成，下次运行时间: {self._next_run_time.isoformat()}")
            
        except ImportError:
            logger.error("适配器模块不可用，无法执行冒烟测试")
        except Exception as e:
            logger.error(f"冒烟测试执行异常: {e}")
        
        return results

    def _test_platform(self, platform: str) -> SmokeTestResult:
        """
        测试单个平台
        
        Returns:
            SmokeTestResult
        """
        start_time = time.time()
        
        try:
            from app.adapters import get_adapter
            
            adapter = get_adapter(platform)
            if adapter is None:
                return SmokeTestResult(
                    platform=platform,
                    timestamp=datetime.utcnow(),
                    success=False,
                    response_time=time.time() - start_time,
                    error_message="适配器不存在"
                )
            
            # 执行检测
            result = adapter.detect(self.SMOKE_TEST_KEYWORD)
            
            response_time = time.time() - start_time
            success = result.get("success", False)
            error_message = result.get("error", "") if not success else ""
            response_preview = result.get("response_content", "")[:200] if success else ""
            
            smoke_result = SmokeTestResult(
                platform=platform,
                timestamp=datetime.utcnow(),
                success=success,
                response_time=response_time,
                error_message=error_message,
                response_preview=response_preview
            )
            
            # 记录结果
            self._record_result(smoke_result)
            self._last_test_time[platform] = datetime.utcnow()
            
            logger.info(f"[冒烟测试] {platform}: {'成功' if success else '失败'} (耗时: {response_time:.2f}秒)")
            
            return smoke_result
            
        except Exception as e:
            response_time = time.time() - start_time
            smoke_result = SmokeTestResult(
                platform=platform,
                timestamp=datetime.utcnow(),
                success=False,
                response_time=response_time,
                error_message=str(e)
            )
            
            # 记录结果
            self._record_result(smoke_result)
            self._last_test_time[platform] = datetime.utcnow()
            
            logger.error(f"[冒烟测试] {platform} 异常: {e}")
            
            return smoke_result

    def _record_result(self, result: SmokeTestResult):
        """记录测试结果"""
        platform = result.platform.lower()
        
        if platform not in self._test_results:
            self._test_results[platform] = []
        
        self._test_results[platform].append(result)
        
        # 保持最多指定数量的记录
        if len(self._test_results[platform]) > self._max_results_per_platform:
            self._test_results[platform] = self._test_results[platform][-self._max_results_per_platform:]

    def _send_alert(self, platform: str, last_result: SmokeTestResult):
        """
        发送告警（当前仅打印日志）
        
        邮件告警在后续实现
        """
        consecutive = self._consecutive_failures.get(platform, 0)
        
        alert_message = f"""
========================================
[冒烟测试告警] 平台: {platform}
========================================
连续失败次数: {consecutive} 次
最近一次测试: {last_result.timestamp.isoformat()}
错误信息: {last_result.error_message}
========================================
建议: 检查 {platform} 平台的 API 配置和网络连接
========================================
"""
        logger.warning(alert_message)

    def get_test_results(self, platform: str = None, limit: int = 10) -> List[dict]:
        """
        获取测试结果记录
        
        Args:
            platform: 平台名称（可选），为 None 则返回所有平台
            limit: 返回记录数
            
        Returns:
            测试结果列表
        """
        if platform:
            platform = platform.lower()
            results = self._test_results.get(platform, [])[-limit:]
            return [r.to_dict() for r in reversed(results)]
        else:
            # 返回所有平台的最近记录
            all_results = []
            for p, results in self._test_results.items():
                all_results.extend(results[-limit:])
            all_results.sort(key=lambda x: x.timestamp, reverse=True)
            return [r.to_dict() for r in all_results[:limit]]

    def get_latest_result(self, platform: str) -> Optional[dict]:
        """获取平台最近一次测试结果"""
        platform = platform.lower()
        results = self._test_results.get(platform, [])
        if results:
            return results[-1].to_dict()
        return None

    def get_consecutive_failures(self, platform: str) -> int:
        """获取连续失败次数"""
        return self._consecutive_failures.get(platform.lower(), 0)

    def get_all_status(self) -> List[dict]:
        """获取所有平台的冒烟测试状态"""
        try:
            from app.adapters import list_supported_platforms
            platforms = list_supported_platforms()
        except ImportError:
            platforms = ["deepseek", "kimi", "doubao"]
        
        status = []
        for platform in platforms:
            latest = self.get_latest_result(platform)
            consecutive = self.get_consecutive_failures(platform)
            
            status.append({
                "platform": platform,
                "last_test": latest,
                "consecutive_failures": consecutive,
                "needs_attention": consecutive >= 2
            })
        
        return status

    def get_next_run_time(self) -> Optional[str]:
        """获取下次运行时间"""
        if self._next_run_time:
            return self._next_run_time.isoformat()
        return None

    def shutdown(self):
        """关闭服务"""
        self._stop_test.set()
        if self._test_thread and self._test_thread.is_alive():
            self._test_thread.join(timeout=5)
        logger.info("冒烟测试服务已关闭")


# 全局冒烟测试服务实例
_smoke_test_service: Optional[SmokeTestService] = None


def get_smoke_test_service() -> SmokeTestService:
    """获取冒烟测试服务实例"""
    global _smoke_test_service
    if _smoke_test_service is None:
        try:
            _smoke_test_service = SmokeTestService()
        except Exception as e:
            logger.error(f"冒烟测试服务初始化失败: {e}")
            # 返回一个禁用版本
            class DisabledSmokeTestService:
                def run_smoke_test(self):
                    return {}
                def get_test_results(self, platform=None, limit=10):
                    return []
                def get_all_status(self):
                    return []
                def get_next_run_time(self):
                    return None
            
            _smoke_test_service = DisabledSmokeTestService()
    return _smoke_test_service
