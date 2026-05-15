"""
PrismaMate 棱镜 - 平台冷却期管理器

按架构文档 1.3 节和第三章风险应对策略实现：
- 触发条件：同一平台连续失败 3 次后，自动进入冷却期
- 冷却时长：2 小时（可配置）
- 执行动作：
  - 将该平台加入冷却集合
  - 标记所有等待该平台的任务状态为 paused
  - 冷却期结束后自动执行探测
  - 探测成功后移出冷却集合，任务恢复
- 日志记录：冷却事件写入内存表
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    yaml = None
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class CooldownEvent:
    """冷却事件记录"""
    platform: str
    event_type: str  # "cooldown_started", "cooldown_ended", "probe_success", "probe_failed"
    timestamp: datetime
    reason: str = ""
    consecutive_failures: int = 0

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "consecutive_failures": self.consecutive_failures
        }


class PlatformCooldownManager:
    """
    平台冷却期管理器（单例）
    
    使用内存存储，MVP 阶段不依赖 Redis
    """

    _instance: Optional["PlatformCooldownManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: str = "config/detection/throttle.yaml"):
        # 防止重复初始化
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        
        # 配置
        self.config = self._load_config(config_path)
        
        # 触发冷却的连续失败次数
        self.failure_threshold = self.config.get("cooldown_on_failure", 3)
        
        # 冷却时长（秒）
        self.cooldown_duration = self.config.get("cooldown_duration", 7200)
        
        # 平台连续失败计数: {platform: failure_count}
        self._failure_counts: Dict[str, int] = {}
        
        # 冷却中的平台: {platform: cooldown_until_timestamp}
        self._cooldown_platforms: Dict[str, float] = {}
        
        # 冷却事件记录（最近 100 条）
        self._cooldown_events: List[CooldownEvent] = []
        self._max_events = 100
        
        # 等待冷却恢复的任务: {platform: [task_id, ...]}
        self._paused_tasks: Dict[str, List[str]] = {}
        
        # 探测线程
        self._probe_thread: Optional[threading.Thread] = None
        self._stop_probe = threading.Event()
        
        # 启动后台探测线程
        self._start_probe_thread()
        
        logger.info(f"冷却期管理器初始化完成: 阈值={self.failure_threshold}次, 冷却时长={self.cooldown_duration}秒")

    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        if not YAML_AVAILABLE:
            logger.warning(f"PyYAML 未安装，使用默认配置")
            return {
                "cooldown_on_failure": 3,
                "cooldown_duration": 7200
            }
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                return config.get("rate_limit", {})
        except Exception as e:
            logger.warning(f"无法加载冷却期配置文件 ({config_path}): {e}")
            return {
                "cooldown_on_failure": 3,
                "cooldown_duration": 7200
            }

    def _start_probe_thread(self):
        """启动后台探测线程"""
        if self._probe_thread is None or not self._probe_thread.is_alive():
            self._stop_probe.clear()
            self._probe_thread = threading.Thread(
                target=self._probe_loop,
                daemon=True,
                name="cooldown-probe"
            )
            self._probe_thread.start()

    def _probe_loop(self):
        """后台探测循环"""
        while not self._stop_probe.is_set():
            try:
                self._check_cooldowns()
            except Exception as e:
                logger.error(f"冷却期探测循环异常: {e}")
            
            # 每 30 秒检查一次
            self._stop_probe.wait(30)

    def _check_cooldowns(self):
        """检查并处理冷却中的平台"""
        current_time = time.time()
        platforms_to_remove = []
        
        for platform, cooldown_until in list(self._cooldown_platforms.items()):
            if current_time >= cooldown_until:
                logger.info(f"平台 {platform} 冷却期结束，开始探测...")
                platforms_to_remove.append(platform)
                
                # 执行探测
                self._probe_platform(platform)
        
        # 移除探测完成的平台
        for platform in platforms_to_remove:
            # 如果探测成功才会移除，否则保持冷却
            if platform not in self._cooldown_platforms:
                logger.info(f"平台 {platform} 探测成功，冷却期结束")

    def _probe_platform(self, platform: str):
        """
        探测平台是否可用
        
        Returns:
            True if platform is available, False otherwise
        """
        try:
            from app.adapters import get_adapter
            
            adapter = get_adapter(platform)
            if adapter is None:
                self._record_event(
                    platform=platform,
                    event_type="probe_failed",
                    reason="适配器不存在",
                    consecutive_failures=0
                )
                return False
            
            # 执行探测请求
            result = adapter.detect("smoke_test")
            
            if result.get("success", False):
                self._record_event(
                    platform=platform,
                    event_type="probe_success",
                    reason="探测成功",
                    consecutive_failures=0
                )
                return True
            else:
                self._record_event(
                    platform=platform,
                    event_type="probe_failed",
                    reason=result.get("error", "探测失败"),
                    consecutive_failures=0
                )
                # 探测失败，重新进入冷却
                self._enter_cooldown(platform, reason=f"探测失败: {result.get('error', '未知')}")
                return False
                
        except ImportError:
            logger.error("适配器模块不可用，无法探测平台")
            return False
        except Exception as e:
            logger.error(f"探测平台 {platform} 异常: {e}")
            self._record_event(
                platform=platform,
                event_type="probe_failed",
                reason=str(e),
                consecutive_failures=0
            )
            # 探测失败，重新进入冷却
            self._enter_cooldown(platform, reason=f"探测异常: {str(e)}")
            return False

    def _record_event(
        self,
        platform: str,
        event_type: str,
        reason: str = "",
        consecutive_failures: int = 0
    ):
        """记录冷却事件"""
        event = CooldownEvent(
            platform=platform,
            event_type=event_type,
            timestamp=datetime.utcnow(),
            reason=reason,
            consecutive_failures=consecutive_failures
        )
        
        self._cooldown_events.append(event)
        
        # 保持最多 100 条记录
        if len(self._cooldown_events) > self._max_events:
            self._cooldown_events = self._cooldown_events[-self._max_events:]
        
        logger.info(f"[冷却事件] {platform}: {event_type} - {reason}")

    def _enter_cooldown(self, platform: str, reason: str = ""):
        """进入冷却期"""
        cooldown_until = time.time() + self.cooldown_duration
        self._cooldown_platforms[platform] = cooldown_until
        
        self._record_event(
            platform=platform,
            event_type="cooldown_started",
            reason=reason,
            consecutive_failures=self._failure_counts.get(platform, 0)
        )
        
        logger.warning(f"平台 {platform} 进入冷却期，预计恢复时间: {datetime.fromtimestamp(cooldown_until).isoformat()}")

    def record_failure(self, platform: str) -> bool:
        """
        记录一次失败
        
        当连续失败达到阈值时，自动进入冷却期
        
        Returns:
            True if entered cooldown, False otherwise
        """
        platform = platform.lower()
        
        # 如果已经在冷却中，不计数
        if self.is_in_cooldown(platform):
            return False
        
        # 增加失败计数
        self._failure_counts[platform] = self._failure_counts.get(platform, 0) + 1
        
        failure_count = self._failure_counts[platform]
        
        if failure_count >= self.failure_threshold:
            self._enter_cooldown(platform, reason=f"连续失败 {failure_count} 次")
            # 重置失败计数
            self._failure_counts[platform] = 0
            return True
        
        return False

    def record_success(self, platform: str):
        """记录一次成功，重置失败计数"""
        platform = platform.lower()
        self._failure_counts[platform] = 0

    def is_in_cooldown(self, platform: str) -> bool:
        """检查平台是否处于冷却期"""
        platform = platform.lower()
        
        if platform not in self._cooldown_platforms:
            return False
        
        current_time = time.time()
        cooldown_until = self._cooldown_platforms[platform]
        
        if current_time >= cooldown_until:
            # 冷却期已过，但还没有探测，先标记为需要探测
            # 不自动移出，等待探测线程处理
            return True
        
        return True

    def get_cooldown_remaining(self, platform: str) -> float:
        """
        获取剩余冷却时间（秒）
        
        Returns:
            剩余时间（秒），0 表示不在冷却中
        """
        platform = platform.lower()
        
        if platform not in self._cooldown_platforms:
            return 0
        
        remaining = self._cooldown_platforms[platform] - time.time()
        return max(0, remaining)

    def get_platform_status(self, platform: str) -> dict:
        """获取平台冷却状态"""
        platform = platform.lower()
        
        return {
            "platform": platform,
            "in_cooldown": self.is_in_cooldown(platform),
            "cooldown_remaining": self.get_cooldown_remaining(platform),
            "cooldown_until": datetime.fromtimestamp(self._cooldown_platforms[platform]).isoformat() 
                if platform in self._cooldown_platforms and self.is_in_cooldown(platform) else None,
            "consecutive_failures": self._failure_counts.get(platform, 0),
            "paused_tasks": self._paused_tasks.get(platform, [])
        }

    def get_all_platforms_status(self) -> List[dict]:
        """获取所有平台状态"""
        try:
            from app.adapters import list_supported_platforms
            platforms = list_supported_platforms()
        except ImportError:
            platforms = ["deepseek", "kimi", "doubao"]
        
        return [self.get_platform_status(p) for p in platforms]

    def get_cooldown_events(self, limit: int = 20) -> List[dict]:
        """获取冷却事件记录"""
        events = self._cooldown_events[-limit:]
        return [e.to_dict() for e in reversed(events)]

    def pause_tasks_for_platform(self, platform: str, task_ids: List[str]):
        """暂停平台的任务"""
        platform = platform.lower()
        if platform not in self._paused_tasks:
            self._paused_tasks[platform] = []
        self._paused_tasks[platform].extend(task_ids)

    def get_paused_tasks(self, platform: str) -> List[str]:
        """获取平台暂停的任务"""
        platform = platform.lower()
        return self._paused_tasks.get(platform, [])

    def clear_paused_tasks(self, platform: str):
        """清除平台暂停的任务"""
        platform = platform.lower()
        self._paused_tasks[platform] = []

    def shutdown(self):
        """关闭管理器"""
        self._stop_probe.set()
        if self._probe_thread and self._probe_thread.is_alive():
            self._probe_thread.join(timeout=5)
        logger.info("冷却期管理器已关闭")


# 全局冷却管理器实例
_cooldown_manager: Optional[PlatformCooldownManager] = None


def get_cooldown_manager() -> PlatformCooldownManager:
    """获取冷却管理器实例"""
    global _cooldown_manager
    if _cooldown_manager is None:
        try:
            _cooldown_manager = PlatformCooldownManager()
        except Exception as e:
            logger.error(f"冷却期管理器初始化失败: {e}")
            # 返回一个禁用版本
            class DisabledCooldownManager:
                def is_in_cooldown(self, platform):
                    return False
                def record_failure(self, platform):
                    return False
                def record_success(self, platform):
                    pass
                def get_cooldown_remaining(self, platform):
                    return 0
                def get_platform_status(self, platform):
                    return {"platform": platform, "in_cooldown": False, "cooldown_remaining": 0}
                def get_all_platforms_status(self):
                    return []
                def get_cooldown_events(self, limit=20):
                    return []
            
            _cooldown_manager = DisabledCooldownManager()
    return _cooldown_manager
