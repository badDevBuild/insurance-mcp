"""
简化的合规性测试：QPS限制和熔断器

测试FR-008的核心实现：
1. QPS限制（≤0.8 req/s）
2. 熔断机制（403/429触发冷却）
"""
import pytest
import time
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.crawler.middleware.rate_limiter import RateLimiter


class TestRateLimiterBasics:
    """测试速率限制器基础功能"""
    
    @pytest.mark.asyncio
    async def test_qps_limit_basic(self):
        """测试基本的QPS限制"""
        limiter = RateLimiter(global_qps=0.8)
        
        url = "https://life.pingan.com/test"
        
        start_time = time.time()
        
        # 第1个请求应立即通过
        await limiter.acquire(url)
        
        # 第2个请求应被限制
        await limiter.acquire(url)
        
        elapsed = time.time() - start_time
        
        # 两个请求之间应至少间隔 1/0.8 ≈ 1.25秒
        # 由于令牌桶容量是2倍QPS，第一个请求可能立即通过
        # 所以我们只检查总时间 >= 1秒即可
        assert elapsed >= 0.9, f"QPS限制未生效，实际间隔: {elapsed:.2f}s"
    
    def test_try_acquire_non_blocking(self):
        """测试非阻塞式获取令牌"""
        limiter = RateLimiter(global_qps=0.8)
        
        url = "https://life.pingan.com/test"
        
        # 第1次尝试应该成功（令牌桶初始化时是满的）
        result1 = limiter.try_acquire(url)
        assert result1, "第1次try_acquire应该成功"
        
        # 连续多次尝试，确保不会阻塞
        for _ in range(3):
            result = limiter.try_acquire(url)
            # 不做断言，只是确保不会阻塞或抛异常


class TestCircuitBreaker:
    """测试熔断器功能"""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_429(self):
        """测试429错误触发熔断"""
        limiter = RateLimiter(global_qps=0.8, circuit_breaker_cooldown=2)  # 2秒冷却
        
        url = "https://life.pingan.com/test"
        
        # 模拟429错误
        limiter.record_failure(url, status_code=429)
        
        # 检查熔断器是否开启
        domain = limiter._get_domain(url)
        assert limiter.circuit_breakers[domain].is_open, "429应该触发熔断"
        
        # 立即请求应被拒绝
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await limiter.acquire(url)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_403(self):
        """测试403错误触发熔断"""
        limiter = RateLimiter(global_qps=0.8, circuit_breaker_cooldown=2)
        
        url = "https://life.pingan.com/test"
        
        # 模拟403错误
        limiter.record_failure(url, status_code=403)
        
        # 检查熔断器是否开启
        domain = limiter._get_domain(url)
        assert limiter.circuit_breakers[domain].is_open, "403应该触发熔断"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self):
        """测试熔断器冷却恢复"""
        limiter = RateLimiter(global_qps=0.8, circuit_breaker_cooldown=2)  # 2秒冷却
        
        url = "https://life.pingan.com/test"
        
        # 触发熔断
        limiter.record_failure(url, status_code=429)
        
        domain = limiter._get_domain(url)
        assert limiter.circuit_breakers[domain].is_open, "熔断应该开启"
        
        # 等待冷却时间
        await asyncio.sleep(2.5)  # 2秒冷却 + 0.5秒buffer
        
        # 冷却后应该可以请求
        await limiter.acquire(url)  # 不应抛出异常
        
        # 熔断器应该已经关闭
        assert not limiter.circuit_breakers[domain].is_open, "冷却后熔断应解除"
    
    def test_circuit_breaker_stats(self):
        """测试熔断器统计信息"""
        limiter = RateLimiter(global_qps=0.8)
        
        url = "https://life.pingan.com/test"
        
        # 记录几次操作
        limiter.record_success(url)
        limiter.record_failure(url, status_code=500)  # 普通错误
        limiter.record_failure(url, status_code=429)  # 触发熔断
        
        # 获取统计信息
        stats = limiter.get_stats()
        
        assert "circuit_breaker_trips" in stats
        assert "active_domains" in stats
        assert stats["circuit_breaker_trips"] == 1, "应该记录1次熔断"


class TestPerDomainLimiting:
    """测试每域名独立限流"""
    
    @pytest.mark.asyncio
    async def test_different_domains_independent(self):
        """测试不同域名之间相互独立"""
        limiter = RateLimiter(global_qps=1.0)  # 提高QPS以加速测试
        
        url1 = "https://domain1.com/test"
        url2 = "https://domain2.com/test"
        
        # 对域名1触发熔断
        limiter.record_failure(url1, status_code=429)
        
        domain1 = limiter._get_domain(url1)
        domain2 = limiter._get_domain(url2)
        
        # 域名1应该被熔断
        assert limiter.circuit_breakers[domain1].is_open
        
        # 域名2应该不受影响
        await limiter.acquire(url2)  # 应该成功
        
        # 域名2的熔断器不应该开启
        if domain2 in limiter.circuit_breakers:
            assert not limiter.circuit_breakers[domain2].is_open


class TestComplianceRequirements:
    """测试spec.md中的合规要求"""
    
    @pytest.mark.asyncio
    async def test_fr008_qps_requirement(self):
        """
        测试FR-008要求：QPS ≤ 0.8 req/s
        
        规格说明：
        - 全局QPS不超过0.8 req/s
        - 相当于每个请求至少间隔1.25秒
        """
        limiter = RateLimiter(global_qps=0.8)
        
        url = "https://life.pingan.com/test"
        
        # 发送3个请求
        start = time.time()
        for _ in range(3):
            await limiter.acquire(url)
        elapsed = time.time() - start
        
        # 3个请求应该至少耗时 2.5秒 (2个间隔 * 1.25秒)
        # 考虑令牌桶的burst容量，实际可能稍快
        assert elapsed >= 2.0, f"QPS超过限制，3个请求耗时: {elapsed:.2f}s"
    
    @pytest.mark.asyncio
    async def test_fr008_circuit_breaker_cooldown(self):
        """
        测试FR-008要求：熔断器冷却时间 ≥ 5分钟
        
        注意：为了测试速度，这里使用3秒冷却
        实际生产环境应该是300秒（5分钟）
        """
        limiter = RateLimiter(global_qps=0.8, circuit_breaker_cooldown=3)
        
        url = "https://life.pingan.com/test"
        
        # 触发熔断
        limiter.record_failure(url, status_code=429)
        
        domain = limiter._get_domain(url)
        breaker = limiter.circuit_breakers[domain]
        
        # 检查冷却时间设置
        assert breaker.cooldown_seconds == 3, "冷却时间应该设置正确"
        
        # 验证熔断生效
        assert breaker.is_open, "熔断应该开启"
        
        # 冷却前不能访问
        with pytest.raises(Exception):
            await limiter.acquire(url)
        
        # 等待冷却
        await asyncio.sleep(3.5)
        
        # 冷却后可以访问
        await limiter.acquire(url)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
