"""
QPS限流器单元测试

测试范围：
- 令牌桶算法基本功能
- 全局QPS限流
- 每域名独立限流
- 熔断机制
- 统计信息
"""

import asyncio
import pytest
import time
from src.crawler.middleware.rate_limiter import (
    TokenBucket,
    CircuitBreaker,
    RateLimiter,
    reset_rate_limiter
)


class TestTokenBucket:
    """测试令牌桶算法"""
    
    def test_initial_state(self):
        """测试初始状态"""
        bucket = TokenBucket(capacity=10.0, tokens_per_second=1.0)
        assert bucket.tokens == 10.0
        assert bucket.capacity == 10.0
        assert bucket.tokens_per_second == 1.0
    
    def test_try_acquire_success(self):
        """测试成功获取令牌"""
        bucket = TokenBucket(capacity=10.0, tokens_per_second=1.0)
        assert bucket.try_acquire(1) is True
        assert bucket.tokens == 9.0
    
    def test_try_acquire_failure(self):
        """测试令牌不足时获取失败"""
        bucket = TokenBucket(capacity=1.0, tokens_per_second=1.0)
        bucket.tokens = 0.5
        assert bucket.try_acquire(1) is False
        # 令牌数应该接近0.5（允许_refill()导致的微小变化）
        assert 0.5 <= bucket.tokens <= 0.6
    
    @pytest.mark.asyncio
    async def test_refill(self):
        """测试令牌补充"""
        bucket = TokenBucket(capacity=10.0, tokens_per_second=2.0)
        bucket.tokens = 0.0
        
        # 等待0.5秒，应该补充1个令牌
        await asyncio.sleep(0.5)
        bucket._refill()
        
        # 允许一定误差（±0.2）
        assert 0.8 <= bucket.tokens <= 1.2
    
    @pytest.mark.asyncio
    async def test_acquire_blocking(self):
        """测试阻塞式获取令牌"""
        bucket = TokenBucket(capacity=1.0, tokens_per_second=2.0)
        bucket.tokens = 0.0
        
        start = time.time()
        success = await bucket.acquire(1)
        elapsed = time.time() - start
        
        assert success is True
        # 应该等待大约0.5秒
        assert 0.3 <= elapsed <= 0.7


class TestCircuitBreaker:
    """测试熔断器"""
    
    def test_initial_state(self):
        """测试初始状态"""
        breaker = CircuitBreaker(cooldown_seconds=5)
        assert breaker.is_open is False
        assert breaker.failure_count == 0
    
    def test_trip(self):
        """测试触发熔断"""
        breaker = CircuitBreaker()
        breaker.trip()
        
        assert breaker.is_open is True
        assert breaker.opened_at is not None
        assert breaker.failure_count == 0
    
    def test_failure_threshold(self):
        """测试失败阈值"""
        breaker = CircuitBreaker(failure_threshold=3)
        
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_open is False
        
        breaker.record_failure()
        assert breaker.is_open is True  # 达到阈值，触发熔断
    
    def test_success_resets_count(self):
        """测试成功请求重置计数"""
        breaker = CircuitBreaker(failure_threshold=3)
        
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2
        
        breaker.record_success()
        assert breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_cooldown(self):
        """测试冷却时间"""
        breaker = CircuitBreaker(cooldown_seconds=1)
        breaker.trip()
        
        assert breaker.attempt_reset() is False  # 冷却期内无法重置
        
        await asyncio.sleep(1.1)
        assert breaker.attempt_reset() is True  # 冷却期结束，成功重置
        assert breaker.is_open is False


class TestRateLimiter:
    """测试全局限流器"""
    
    def setup_method(self):
        """每个测试前重置限流器"""
        reset_rate_limiter()
    
    @pytest.mark.asyncio
    async def test_global_qps_limit(self):
        """测试全局QPS限制"""
        limiter = RateLimiter(global_qps=2.0)
        
        # 先消耗所有初始令牌（burst capacity）
        await limiter.acquire("http://example.com/warmup1")
        await limiter.acquire("http://example.com/warmup2")
        await limiter.acquire("http://example.com/warmup3")
        await limiter.acquire("http://example.com/warmup4")
        
        start = time.time()
        
        # 现在令牌桶应该空了，发送3个请求
        await limiter.acquire("http://example.com/1")
        await limiter.acquire("http://example.com/2")
        await limiter.acquire("http://example.com/3")
        
        elapsed = time.time() - start
        
        # 3个请求，2 QPS，应该需要至少1秒
        assert elapsed >= 1.0
        assert elapsed <= 2.0
    
    @pytest.mark.asyncio
    async def test_per_domain_limit(self):
        """测试每域名独立限流"""
        limiter = RateLimiter(global_qps=10.0, per_domain_qps=1.0)
        
        # 先消耗初始令牌
        await limiter.acquire("http://example.com/warmup1")
        await limiter.acquire("http://example.com/warmup2")
        
        start = time.time()
        
        # 同一域名发送2个请求
        await limiter.acquire("http://example.com/1")
        await limiter.acquire("http://example.com/2")
        
        elapsed = time.time() - start
        
        # 1 QPS，2个请求应该需要至少1秒
        assert elapsed >= 1.0
    
    @pytest.mark.asyncio
    async def test_different_domains_parallel(self):
        """测试不同域名可以并行"""
        limiter = RateLimiter(global_qps=10.0, per_domain_qps=1.0)
        
        start = time.time()
        
        # 不同域名应该可以并行
        await asyncio.gather(
            limiter.acquire("http://example1.com/page"),
            limiter.acquire("http://example2.com/page")
        )
        
        elapsed = time.time() - start
        
        # 全局QPS足够高，应该几乎同时完成
        assert elapsed < 1.0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_trip(self):
        """测试熔断器触发"""
        limiter = RateLimiter(
            global_qps=10.0,
            circuit_breaker_enabled=True
        )
        
        url = "http://blocked-domain.com/page"
        
        # 触发熔断（429状态码）
        limiter.record_failure(url, status_code=429)
        
        # 尝试获取许可应该失败
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await limiter.acquire(url)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_reset(self):
        """测试熔断器重置"""
        limiter = RateLimiter(
            global_qps=10.0,
            circuit_breaker_enabled=True,
            circuit_breaker_cooldown=1  # 1秒冷却
        )
        
        url = "http://blocked-domain.com/page"
        
        # 触发熔断
        limiter.record_failure(url, status_code=429)
        
        # 等待冷却时间
        await asyncio.sleep(1.1)
        
        # 应该可以重新获取许可
        success = await limiter.acquire(url)
        assert success is True
    
    def test_record_success(self):
        """测试记录成功"""
        limiter = RateLimiter(global_qps=1.0)
        url = "http://example.com/page"
        
        # 记录失败
        limiter.record_failure(url)
        limiter.record_failure(url)
        
        # 记录成功应该重置失败计数
        limiter.record_success(url)
        
        domain = limiter._get_domain(url)
        assert limiter.circuit_breakers[domain].failure_count == 0
    
    def test_stats(self):
        """测试统计信息"""
        limiter = RateLimiter(global_qps=1.0)
        
        stats = limiter.get_stats()
        assert "total_requests" in stats
        assert "blocked_requests" in stats
        assert "circuit_breaker_trips" in stats
        assert "active_domains" in stats
    
    def test_try_acquire_non_blocking(self):
        """测试非阻塞获取"""
        limiter = RateLimiter(global_qps=0.5)  # 0.5 QPS = 2秒/请求
        
        url = "http://example.com/page"
        
        # 第一次应该成功
        assert limiter.try_acquire(url) is True
        
        # 立即再次请求应该失败（令牌不足）
        assert limiter.try_acquire(url) is False
    
    @pytest.mark.asyncio
    async def test_403_triggers_circuit_breaker(self):
        """测试403状态码触发熔断"""
        limiter = RateLimiter(global_qps=10.0, circuit_breaker_enabled=True)
        url = "http://forbidden.com/page"
        
        # 403应该立即触发熔断
        limiter.record_failure(url, status_code=403)
        
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await limiter.acquire(url)
    
    def test_manual_reset_circuit_breaker(self):
        """测试手动重置熔断器"""
        limiter = RateLimiter(global_qps=10.0)
        url = "http://blocked.com/page"
        domain = limiter._get_domain(url)
        
        # 触发熔断
        limiter.record_failure(url, status_code=429)
        assert limiter.circuit_breakers[domain].is_open is True
        
        # 手动重置
        limiter.reset_circuit_breaker(domain)
        assert limiter.circuit_breakers[domain].is_open is False


class TestIntegration:
    """集成测试"""
    
    def setup_method(self):
        """每个测试前重置限流器"""
        reset_rate_limiter()
    
    @pytest.mark.asyncio
    async def test_realistic_crawling_scenario(self):
        """测试真实爬虫场景"""
        limiter = RateLimiter(
            global_qps=2.0,
            per_domain_qps=1.0,
            circuit_breaker_enabled=True
        )
        
        base_url = "http://example.com"
        
        # 先消耗burst capacity
        await limiter.acquire(f"{base_url}/warmup")
        await limiter.acquire(f"{base_url}/warmup2")
        
        urls = [f"{base_url}/page{i}" for i in range(5)]
        
        start = time.time()
        
        # 模拟爬取5个页面
        for url in urls:
            await limiter.acquire(url)
            limiter.record_success(url)
        
        elapsed = time.time() - start
        
        # 5个请求，1 QPS，应该需要至少4秒
        assert elapsed >= 4.0
        
        # 验证统计信息
        stats = limiter.get_stats()
        assert stats["total_requests"] == 7  # 包括2个warmup请求
        assert stats["blocked_requests"] == 0
        assert stats["active_domains"] >= 1

