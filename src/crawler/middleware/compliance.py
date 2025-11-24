import time
import asyncio
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse
from src.common.config import config
from src.common.logging import logger

class ComplianceManager:
    """
    Manages compliance with Robots.txt and Rate Limiting.
    """
    
    def __init__(self):
        self.robots_parsers = {}
        self.last_request_time = 0.0
        self.delay = config.DOWNLOAD_DELAY
        
    async def wait_for_slot(self):
        """Enforce rate limiting."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.delay:
            wait_time = self.delay - elapsed
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        self.last_request_time = time.time()
        
    def can_fetch(self, url: str) -> bool:
        """
        Check if URL is allowed by robots.txt.
        Parses and caches robots.txt for the domain.
        """
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        if base_url not in self.robots_parsers:
            robots_url = f"{base_url}/robots.txt"
            parser = RobotFileParser()
            try:
                parser.set_url(robots_url)
                parser.read()
                self.robots_parsers[base_url] = parser
                logger.info(f"Loaded robots.txt for {base_url}")
            except Exception as e:
                logger.warning(f"Could not read robots.txt for {base_url}: {e}. Assuming allowed.")
                # If robots.txt fails, usually defaults to allow, or strictly disallow.
                # For this specific project, we should be careful.
                # But if it doesn't exist (404), it means allow all.
                # We'll create a dummy parser that allows all.
                parser.allow_all = True
                self.robots_parsers[base_url] = parser
                
        return self.robots_parsers[base_url].can_fetch(config.USER_AGENT, url)

compliance = ComplianceManager()

