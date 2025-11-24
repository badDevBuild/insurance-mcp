import aiohttp
import asyncio
import random
from pathlib import Path
from typing import Optional
from src.common.logging import logger
from src.common.config import config
from src.crawler.middleware.rate_limiter import get_rate_limiter

class PDFDownloader:
    """
    Async downloader with exponential backoff retry logic and QPS rate limiting.
    
    Features:
    - Exponential backoff retry (FR-008)
    - Global QPS rate limiting (FR-008)
    - Circuit breaker for blocked domains (EC-003)
    """
    
    def __init__(self, max_retries: int = 3, initial_delay: float = 1.0, enable_rate_limit: bool = True):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.enable_rate_limit = enable_rate_limit
        
        # 初始化全局限流器
        if self.enable_rate_limit:
            self.rate_limiter = get_rate_limiter(
                global_qps=config.GLOBAL_QPS,
                per_domain_qps=config.PER_DOMAIN_QPS,
                circuit_breaker_enabled=config.CIRCUIT_BREAKER_ENABLED
            )
        
    async def download(self, url: str, save_path: Path) -> bool:
        """
        Download a file from URL to save_path with retries and rate limiting.
        
        Args:
            url: Source URL
            save_path: Local destination path
            
        Returns:
            True if successful, False otherwise.
        """
        delay = self.initial_delay
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # QPS限流 (FR-008)
                if self.enable_rate_limit:
                    try:
                        await self.rate_limiter.acquire(url)
                    except Exception as e:
                        # 熔断器开启，域名被封锁
                        logger.error(f"Rate limiter blocked request: {e}")
                        return False
                
                async with aiohttp.ClientSession(headers={"User-Agent": config.USER_AGENT}) as session:
                    async with session.get(url, timeout=30) as response:
                        status_code = response.status
                        
                        if status_code == 200:
                            content = await response.read()
                            
                            # Ensure directory exists
                            save_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            with open(save_path, "wb") as f:
                                f.write(content)
                            
                            # 记录成功
                            if self.enable_rate_limit:
                                self.rate_limiter.record_success(url)
                            
                            logger.info(f"Downloaded {url} to {save_path}")
                            return True
                        
                        elif status_code in (429, 403):
                            # 被限流或封禁，触发熔断 (EC-003)
                            logger.warning(f"Rate limited by server: {url} - Status {status_code}")
                            if self.enable_rate_limit:
                                self.rate_limiter.record_failure(url, status_code)
                            return False
                        
                        else:
                            logger.warning(f"Failed to download {url}: Status {status_code}")
                            if self.enable_rate_limit:
                                self.rate_limiter.record_failure(url, status_code)
                            
            except asyncio.TimeoutError:
                logger.warning(f"Attempt {attempt}/{self.max_retries} timeout for {url}")
                if self.enable_rate_limit:
                    self.rate_limiter.record_failure(url)
            except Exception as e:
                logger.warning(f"Attempt {attempt}/{self.max_retries} failed for {url}: {e}")
                if self.enable_rate_limit:
                    self.rate_limiter.record_failure(url)
            
            if attempt < self.max_retries:
                # Exponential backoff with jitter
                sleep_time = delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                logger.info(f"Retrying in {sleep_time:.2f}s...")
                await asyncio.sleep(sleep_time)
                
        logger.error(f"Failed to download {url} after {self.max_retries} attempts")
        return False
    
    def get_rate_limiter_stats(self) -> dict:
        """获取限流器统计信息"""
        if self.enable_rate_limit:
            return self.rate_limiter.get_stats()
        return {}

if __name__ == "__main__":
    async def test():
        downloader = PDFDownloader()
        # Test with a sample PDF (using a placeholder or a real one if known)
        # await downloader.download("http://example.com/test.pdf", Path("data/raw/test.pdf"))
        pass
    # asyncio.run(test())

