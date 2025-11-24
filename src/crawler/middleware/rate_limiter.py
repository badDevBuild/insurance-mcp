"""
全局QPS限流器

基于令牌桶算法实现的QPS限流器，支持：
- 全局QPS限制
- 每域名独立限流
- 熔断机制（域名被封锁时自动暂停）

符合FR-008和EC-003要求。
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional
from urllib.parse import urlparse

from src.common.logging import logger


@dataclass
class CircuitBreaker:
    """
    熔断器状态
    
    当域名被封锁（429/403错误）时，自动进入熔断状态，
    暂停该域名的请求一段时间（默认5分钟）。
    """
    is_open: bool = False  # 熔断器是否开启
    opened_at: Optional[datetime] = None  # 熔断开启时间
    cooldown_seconds: int = 300  # 冷却时间（秒），默认5分钟
    failure_count: int = 0  # 失败次数
    failure_threshold: int = 3  # 失败阈值
    
    def trip(self):
        """触发熔断"""
        self.is_open = True
        self.opened_at = datetime.now()
        self.failure_count = 0
        logger.warning(f"Circuit breaker tripped. Cooldown: {self.cooldown_seconds}s")
    
    def attempt_reset(self) -> bool:
        """尝试重置熔断器"""
        if not self.is_open:
            return True
        
        if self.opened_at and datetime.now() - self.opened_at > timedelta(seconds=self.cooldown_seconds):
            self.is_open = False
            self.opened_at = None
            logger.info("Circuit breaker reset")
            return True
        
        return False
    
    def record_failure(self):
        """记录失败"""
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.trip()
    
    def record_success(self):
        """记录成功"""
        self.failure_count = 0


@dataclass
class TokenBucket:
    """
    令牌桶算法实现
    
    每秒补充tokens_per_second个令牌，最多存储capacity个令牌。
    每次请求消耗1个令牌。
    """
    capacity: float  # 桶容量（令牌数）
    tokens_per_second: float  # 每秒补充的令牌数
    tokens: float = field(default=0.0)  # 当前令牌数
    last_update: float = field(default_factory=time.time)  # 上次更新时间
    
    def __post_init__(self):
        self.tokens = self.capacity  # 初始化为满桶
    
    def _refill(self):
        """补充令牌"""
        now = time.time()
        elapsed = now - self.last_update
        
        # 计算应该补充的令牌数
        new_tokens = elapsed * self.tokens_per_second
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_update = now
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        获取令牌（异步，会等待）
        
        Args:
            tokens: 需要的令牌数，默认1
            
        Returns:
            bool: 是否成功获取令牌
        """
        while True:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            # 计算需要等待的时间
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.tokens_per_second
            
            # 等待一小段时间后重试
            await asyncio.sleep(min(wait_time, 1.0))  # 最多等待1秒
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """
        尝试获取令牌（非阻塞）
        
        Args:
            tokens: 需要的令牌数，默认1
            
        Returns:
            bool: 是否成功获取令牌
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        return False


class RateLimiter:
    """
    全局QPS限流器
    
    特性：
    - 全局QPS限制
    - 每域名独立限流
    - 熔断机制
    - 线程安全（使用asyncio）
    
    使用示例：
        limiter = RateLimiter(global_qps=1.0)
        await limiter.acquire("https://example.com/path")
    """
    
    def __init__(
        self,
        global_qps: float = 1.0,
        per_domain_qps: Optional[float] = None,
        circuit_breaker_enabled: bool = True,
        circuit_breaker_cooldown: int = 300  # 5分钟
    ):
        """
        初始化限流器
        
        Args:
            global_qps: 全局每秒请求数限制（默认1.0）
            per_domain_qps: 每个域名的QPS限制（None表示不限制）
            circuit_breaker_enabled: 是否启用熔断机制
            circuit_breaker_cooldown: 熔断冷却时间（秒）
        """
        self.global_qps = global_qps
        self.per_domain_qps = per_domain_qps or global_qps
        
        # 全局令牌桶
        self.global_bucket = TokenBucket(
            capacity=global_qps * 2,  # 容量为2倍QPS，允许短时burst
            tokens_per_second=global_qps
        )
        
        # 每个域名的令牌桶
        self.domain_buckets: Dict[str, TokenBucket] = {}
        
        # 每个域名的熔断器
        self.circuit_breakers: Dict[str, CircuitBreaker] = defaultdict(
            lambda: CircuitBreaker(cooldown_seconds=circuit_breaker_cooldown)
        ) if circuit_breaker_enabled else {}
        
        self.circuit_breaker_enabled = circuit_breaker_enabled
        
        # 统计信息
        self.stats = {
            "total_requests": 0,
            "blocked_requests": 0,
            "circuit_breaker_trips": 0
        }
        
        logger.info(f"RateLimiter initialized: global_qps={global_qps}, per_domain_qps={per_domain_qps}")
    
    def _get_domain(self, url: str) -> str:
        """从URL提取域名"""
        parsed = urlparse(url)
        return parsed.netloc or "unknown"
    
    def _get_domain_bucket(self, domain: str) -> TokenBucket:
        """获取或创建域名令牌桶"""
        if domain not in self.domain_buckets:
            self.domain_buckets[domain] = TokenBucket(
                capacity=self.per_domain_qps * 2,
                tokens_per_second=self.per_domain_qps
            )
        return self.domain_buckets[domain]
    
    async def acquire(self, url: str) -> bool:
        """
        获取访问许可（会等待直到获得许可）
        
        Args:
            url: 目标URL
            
        Returns:
            bool: 是否获得许可
            
        Raises:
            Exception: 如果熔断器处于开启状态
        """
        self.stats["total_requests"] += 1
        
        domain = self._get_domain(url)
        
        # 检查熔断器
        if self.circuit_breaker_enabled and domain in self.circuit_breakers:
            breaker = self.circuit_breakers[domain]
            
            # 尝试重置熔断器
            if not breaker.attempt_reset():
                self.stats["blocked_requests"] += 1
                remaining = breaker.cooldown_seconds - (datetime.now() - breaker.opened_at).seconds
                raise Exception(
                    f"Circuit breaker is open for domain {domain}. "
                    f"Retry after {remaining}s"
                )
        
        # 全局限流
        await self.global_bucket.acquire()
        
        # 域名级限流
        domain_bucket = self._get_domain_bucket(domain)
        await domain_bucket.acquire()
        
        logger.debug(f"Rate limiter: Acquired permission for {domain}")
        return True
    
    def try_acquire(self, url: str) -> bool:
        """
        尝试获取访问许可（非阻塞）
        
        Args:
            url: 目标URL
            
        Returns:
            bool: 是否获得许可
        """
        domain = self._get_domain(url)
        
        # 检查熔断器
        if self.circuit_breaker_enabled and domain in self.circuit_breakers:
            breaker = self.circuit_breakers[domain]
            if not breaker.attempt_reset():
                self.stats["blocked_requests"] += 1
                return False
        
        # 全局限流
        if not self.global_bucket.try_acquire():
            return False
        
        # 域名级限流
        domain_bucket = self._get_domain_bucket(domain)
        if not domain_bucket.try_acquire():
            # 归还全局令牌
            self.global_bucket.tokens += 1
            return False
        
        return True
    
    def record_success(self, url: str):
        """记录请求成功"""
        if not self.circuit_breaker_enabled:
            return
        
        domain = self._get_domain(url)
        if domain in self.circuit_breakers:
            self.circuit_breakers[domain].record_success()
    
    def record_failure(self, url: str, status_code: Optional[int] = None):
        """
        记录请求失败
        
        Args:
            url: 目标URL
            status_code: HTTP状态码（429或403会触发熔断）
        """
        if not self.circuit_breaker_enabled:
            return
        
        domain = self._get_domain(url)
        
        # 429 (Too Many Requests) 或 403 (Forbidden) 触发熔断
        if status_code in (429, 403):
            breaker = self.circuit_breakers[domain]
            breaker.trip()
            self.stats["circuit_breaker_trips"] += 1
            logger.warning(
                f"Circuit breaker tripped for {domain} due to status {status_code}"
            )
        else:
            # 其他错误累积计数
            self.circuit_breakers[domain].record_failure()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "active_domains": len(self.domain_buckets),
            "circuit_breakers_open": sum(
                1 for cb in self.circuit_breakers.values() if cb.is_open
            ) if self.circuit_breaker_enabled else 0
        }
    
    def reset_circuit_breaker(self, domain: str):
        """手动重置指定域名的熔断器"""
        if domain in self.circuit_breakers:
            self.circuit_breakers[domain].is_open = False
            self.circuit_breakers[domain].opened_at = None
            self.circuit_breakers[domain].failure_count = 0
            logger.info(f"Circuit breaker manually reset for {domain}")


# 全局限流器实例（单例）
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(
    global_qps: float = 1.0,
    per_domain_qps: Optional[float] = None,
    circuit_breaker_enabled: bool = True
) -> RateLimiter:
    """
    获取全局限流器实例（单例模式）
    
    Args:
        global_qps: 全局每秒请求数限制
        per_domain_qps: 每个域名的QPS限制
        circuit_breaker_enabled: 是否启用熔断机制
        
    Returns:
        RateLimiter: 全局限流器实例
    """
    global _rate_limiter
    
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            global_qps=global_qps,
            per_domain_qps=per_domain_qps,
            circuit_breaker_enabled=circuit_breaker_enabled
        )
    
    return _rate_limiter


def reset_rate_limiter():
    """重置全局限流器（主要用于测试）"""
    global _rate_limiter
    _rate_limiter = None

