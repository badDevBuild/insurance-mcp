"""审计日志模块单元测试"""

import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from src.crawler.middleware.audit_logger import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    get_audit_logger
)


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as f:
        yield Path(f.name)


@pytest.fixture
def audit_logger(temp_db):
    """创建测试用审计日志器"""
    return AuditLogger(db_path=temp_db)


class TestAuditEvent:
    """AuditEvent数据类测试"""
    
    def test_to_dict(self):
        """测试转换为字典"""
        event = AuditEvent(
            event_type=AuditEventType.DOWNLOAD_SUCCESS,
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            company="平安人寿",
            product_code="P123",
            file_hash="abc123"
        )
        result = event.to_dict()
        assert result['event_type'] == "download_success"
        assert result['timestamp'] == "2025-01-01T12:00:00"
        assert result['company'] == "平安人寿"
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            'event_type': 'download_success',
            'timestamp': '2025-01-01T12:00:00',
            'company': '平安人寿',
            'product_code': 'P123',
            'product_name': None,
            'url': None,
            'status': None,
            'file_hash': 'abc123',
            'file_size': None,
            'error_message': None,
            'retry_count': None,
            'duration_ms': None,
            'metadata': {}
        }
        event = AuditEvent.from_dict(data)
        assert event.event_type == AuditEventType.DOWNLOAD_SUCCESS
        assert event.company == "平安人寿"


class TestAuditLogger:
    """AuditLogger类测试"""
    
    def test_init_creates_db(self, temp_db):
        """测试初始化创建数据库"""
        logger = AuditLogger(db_path=temp_db)
        assert temp_db.exists()
    
    def test_log_discovery_start(self, audit_logger):
        """测试记录发现开始"""
        audit_logger.log_discovery_start("平安人寿", source_url="http://example.com")
        events = audit_logger.query_events(event_type=AuditEventType.DISCOVERY_START)
        assert len(events) == 1
        assert events[0].company == "平安人寿"
    
    def test_log_discovery_success(self, audit_logger):
        """测试记录发现成功"""
        audit_logger.log_discovery_success("平安人寿", product_count=45, duration_ms=5000)
        events = audit_logger.query_events(event_type=AuditEventType.DISCOVERY_SUCCESS)
        assert len(events) == 1
        assert events[0].metadata.get('product_count') == 45
        assert events[0].duration_ms == 5000
    
    def test_log_discovery_failed(self, audit_logger):
        """测试记录发现失败"""
        audit_logger.log_discovery_failed("平安人寿", "连接超时")
        events = audit_logger.query_events(event_type=AuditEventType.DISCOVERY_FAILED)
        assert len(events) == 1
        assert events[0].error_message == "连接超时"
    
    def test_log_download_success(self, audit_logger):
        """测试记录下载成功"""
        audit_logger.log_download_success(
            product_code="P123",
            url="http://example.com/doc.pdf",
            file_hash="abc123def456",
            file_size=1024000,
            company="平安人寿",
            product_name="平安福耀年金保险"
        )
        events = audit_logger.query_events(event_type=AuditEventType.DOWNLOAD_SUCCESS)
        assert len(events) == 1
        assert events[0].product_code == "P123"
        assert events[0].file_hash == "abc123def456"
        assert events[0].file_size == 1024000
    
    def test_log_download_failed(self, audit_logger):
        """测试记录下载失败"""
        audit_logger.log_download_failed(
            product_code="P456",
            url="http://example.com/doc.pdf",
            error="HTTP 404",
            retry_count=3
        )
        events = audit_logger.query_events(event_type=AuditEventType.DOWNLOAD_FAILED)
        assert len(events) == 1
        assert events[0].error_message == "HTTP 404"
        assert events[0].retry_count == 3
    
    def test_log_download_retry(self, audit_logger):
        """测试记录下载重试"""
        audit_logger.log_download_retry(
            product_code="P789",
            url="http://example.com/doc.pdf",
            retry_count=2,
            error="连接超时"
        )
        events = audit_logger.query_events(event_type=AuditEventType.DOWNLOAD_RETRY)
        assert len(events) == 1
        assert events[0].retry_count == 2
    
    def test_log_rate_limited(self, audit_logger):
        """测试记录限流"""
        audit_logger.log_rate_limited(
            url="http://example.com/api",
            company="平安人寿",
            wait_seconds=1.5
        )
        events = audit_logger.query_events(event_type=AuditEventType.RATE_LIMITED)
        assert len(events) == 1
        assert events[0].metadata.get('wait_seconds') == 1.5
    
    def test_log_circuit_breaker(self, audit_logger):
        """测试记录熔断"""
        audit_logger.log_circuit_breaker(
            domain="life.pingan.com",
            cooldown_seconds=300,
            trigger_reason="429 Too Many Requests"
        )
        events = audit_logger.query_events(event_type=AuditEventType.CIRCUIT_BREAKER)
        assert len(events) == 1
        assert events[0].error_message == "429 Too Many Requests"
        assert events[0].metadata.get('cooldown_seconds') == 300
    
    def test_log_robots_blocked(self, audit_logger):
        """测试记录robots阻止"""
        audit_logger.log_robots_blocked(
            url="http://example.com/private/",
            company="平安人寿"
        )
        events = audit_logger.query_events(event_type=AuditEventType.ROBOTS_BLOCKED)
        assert len(events) == 1
        assert events[0].status == "blocked"


class TestQueryMethods:
    """查询方法测试"""
    
    def test_query_by_company(self, audit_logger):
        """测试按公司查询"""
        audit_logger.log_discovery_success("平安人寿", product_count=45)
        audit_logger.log_discovery_success("中国人寿", product_count=30)
        
        events = audit_logger.query_events(company="平安")
        assert len(events) == 1
        assert events[0].company == "平安人寿"
    
    def test_query_by_product_code(self, audit_logger):
        """测试按产品代码查询"""
        audit_logger.log_download_success("P123", "http://...", "abc", 1024)
        audit_logger.log_download_success("P456", "http://...", "def", 2048)
        
        events = audit_logger.query_events(product_code="P123")
        assert len(events) == 1
        assert events[0].product_code == "P123"
    
    def test_query_by_time_range(self, audit_logger):
        """测试按时间范围查询"""
        audit_logger.log_discovery_success("平安人寿", product_count=45)
        
        # 查询未来时间范围，应该没有结果
        future = datetime.now() + timedelta(days=1)
        events = audit_logger.query_events(start_time=future)
        assert len(events) == 0
        
        # 查询过去时间范围，应该有结果
        past = datetime.now() - timedelta(days=1)
        events = audit_logger.query_events(start_time=past)
        assert len(events) == 1
    
    def test_query_limit(self, audit_logger):
        """测试查询数量限制"""
        for i in range(20):
            audit_logger.log_discovery_success(f"公司{i}", product_count=i)
        
        events = audit_logger.query_events(limit=5)
        assert len(events) == 5


class TestStatistics:
    """统计方法测试"""
    
    def test_get_statistics(self, audit_logger):
        """测试获取统计信息"""
        # 添加一些测试数据
        audit_logger.log_download_success("P1", "http://...", "abc", 1024, company="平安人寿")
        audit_logger.log_download_success("P2", "http://...", "def", 2048, company="平安人寿")
        audit_logger.log_download_failed("P3", "http://...", "error", company="中国人寿")
        
        stats = audit_logger.get_statistics()
        
        assert stats['event_counts'].get('download_success', 0) == 2
        assert stats['event_counts'].get('download_failed', 0) == 1
        assert stats['total_downloaded_size_bytes'] == 3072
        assert stats['success_rate'] == pytest.approx(66.67, 0.1)
    
    def test_get_statistics_by_company(self, audit_logger):
        """测试按公司获取统计"""
        audit_logger.log_download_success("P1", "http://...", "abc", 1024, company="平安人寿")
        audit_logger.log_download_success("P2", "http://...", "def", 2048, company="中国人寿")
        
        stats = audit_logger.get_statistics(company="平安")
        assert stats['event_counts'].get('download_success', 0) == 1
    
    def test_get_recent_failures(self, audit_logger):
        """测试获取最近失败事件"""
        audit_logger.log_download_failed("P1", "http://...", "error1")
        audit_logger.log_download_failed("P2", "http://...", "error2")
        audit_logger.log_download_success("P3", "http://...", "abc", 1024)
        
        failures = audit_logger.get_recent_failures(limit=10)
        assert len(failures) == 2
        assert all(e.event_type == AuditEventType.DOWNLOAD_FAILED for e in failures)
    
    def test_get_download_history(self, audit_logger):
        """测试获取产品下载历史"""
        audit_logger.log_download_start("P123", "http://...")
        audit_logger.log_download_retry("P123", "http://...", 1, "timeout")
        audit_logger.log_download_success("P123", "http://...", "abc", 1024)
        audit_logger.log_download_success("P456", "http://...", "def", 2048)
        
        history = audit_logger.get_download_history("P123")
        assert len(history) == 3
        assert all(e.product_code == "P123" for e in history)


class TestSingleton:
    """单例模式测试"""
    
    def test_get_audit_logger_singleton(self):
        """测试全局单例"""
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()
        assert logger1 is logger2
