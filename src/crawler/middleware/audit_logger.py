"""爬虫审计日志模块

实现Constitution 2.2要求的来源可追溯性，记录所有爬虫操作。

功能:
- 记录产品发现操作
- 记录PDF下载操作
- 记录失败和重试
- 支持按时间、公司、产品查询日志
"""

import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
import sqlite3
from contextlib import contextmanager

from src.common.config import config

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """审计事件类型"""
    DISCOVERY_START = "discovery_start"      # 开始发现产品
    DISCOVERY_SUCCESS = "discovery_success"  # 发现产品成功
    DISCOVERY_FAILED = "discovery_failed"    # 发现产品失败
    DOWNLOAD_START = "download_start"        # 开始下载
    DOWNLOAD_SUCCESS = "download_success"    # 下载成功
    DOWNLOAD_FAILED = "download_failed"      # 下载失败
    DOWNLOAD_RETRY = "download_retry"        # 下载重试
    RATE_LIMITED = "rate_limited"            # 触发限流
    CIRCUIT_BREAKER = "circuit_breaker"      # 触发熔断
    ROBOTS_BLOCKED = "robots_blocked"        # robots.txt阻止


@dataclass
class AuditEvent:
    """审计事件数据结构"""
    event_type: AuditEventType
    timestamp: datetime
    company: str
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    url: Optional[str] = None
    status: Optional[str] = None
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: Optional[int] = None
    duration_ms: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result['event_type'] = self.event_type.value
        result['timestamp'] = self.timestamp.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEvent':
        """从字典创建"""
        data['event_type'] = AuditEventType(data['event_type'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class AuditLogger:
    """爬虫审计日志记录器
    
    支持SQLite持久化存储，提供查询接口。
    
    使用示例:
        audit = AuditLogger()
        audit.log_discovery("平安人寿", product_count=45)
        audit.log_download("P123", "http://...", "success", "abc123")
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """初始化审计日志器
        
        Args:
            db_path: SQLite数据库路径，默认使用config.DB_DIR / "audit.sqlite"
        """
        self.db_path = db_path or (config.DB_DIR / "audit.sqlite")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info(f"审计日志初始化: {self.db_path}")
    
    def _init_db(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    company TEXT NOT NULL,
                    product_code TEXT,
                    product_name TEXT,
                    url TEXT,
                    status TEXT,
                    file_hash TEXT,
                    file_size INTEGER,
                    error_message TEXT,
                    retry_count INTEGER,
                    duration_ms INTEGER,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 创建索引以支持高效查询
            conn.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON audit_events(event_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_events(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_company ON audit_events(company)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_product_code ON audit_events(product_code)")
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _save_event(self, event: AuditEvent):
        """保存审计事件到数据库"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO audit_events (
                    event_type, timestamp, company, product_code, product_name,
                    url, status, file_hash, file_size, error_message,
                    retry_count, duration_ms, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_type.value,
                event.timestamp.isoformat(),
                event.company,
                event.product_code,
                event.product_name,
                event.url,
                event.status,
                event.file_hash,
                event.file_size,
                event.error_message,
                event.retry_count,
                event.duration_ms,
                json.dumps(event.metadata, ensure_ascii=False) if event.metadata else None
            ))
            conn.commit()
        logger.debug(f"审计事件已记录: {event.event_type.value} - {event.company}")
    
    # ==================== 日志记录方法 ====================
    
    def log_discovery_start(self, company: str, **kwargs):
        """记录开始发现产品"""
        event = AuditEvent(
            event_type=AuditEventType.DISCOVERY_START,
            timestamp=datetime.now(),
            company=company,
            metadata=kwargs
        )
        self._save_event(event)
        logger.info(f"[审计] 开始发现产品: {company}")
    
    def log_discovery_success(self, company: str, product_count: int, 
                              duration_ms: Optional[int] = None, **kwargs):
        """记录发现产品成功
        
        Args:
            company: 保险公司名称
            product_count: 发现的产品数量
            duration_ms: 耗时（毫秒）
        """
        event = AuditEvent(
            event_type=AuditEventType.DISCOVERY_SUCCESS,
            timestamp=datetime.now(),
            company=company,
            duration_ms=duration_ms,
            metadata={"product_count": product_count, **kwargs}
        )
        self._save_event(event)
        logger.info(f"[审计] 发现产品成功: {company}, 数量: {product_count}")
    
    def log_discovery_failed(self, company: str, error: str, **kwargs):
        """记录发现产品失败"""
        event = AuditEvent(
            event_type=AuditEventType.DISCOVERY_FAILED,
            timestamp=datetime.now(),
            company=company,
            error_message=error,
            metadata=kwargs
        )
        self._save_event(event)
        logger.error(f"[审计] 发现产品失败: {company}, 错误: {error}")
    
    def log_download_start(self, product_code: str, url: str, 
                           company: str = "未知", product_name: Optional[str] = None):
        """记录开始下载"""
        event = AuditEvent(
            event_type=AuditEventType.DOWNLOAD_START,
            timestamp=datetime.now(),
            company=company,
            product_code=product_code,
            product_name=product_name,
            url=url
        )
        self._save_event(event)
        logger.debug(f"[审计] 开始下载: {product_code} - {url}")
    
    def log_download_success(self, product_code: str, url: str, 
                              file_hash: str, file_size: int,
                              company: str = "未知", 
                              product_name: Optional[str] = None,
                              duration_ms: Optional[int] = None):
        """记录下载成功
        
        Args:
            product_code: 产品代码
            url: 下载URL
            file_hash: 文件哈希值
            file_size: 文件大小（字节）
            company: 保险公司
            product_name: 产品名称
            duration_ms: 耗时（毫秒）
        """
        event = AuditEvent(
            event_type=AuditEventType.DOWNLOAD_SUCCESS,
            timestamp=datetime.now(),
            company=company,
            product_code=product_code,
            product_name=product_name,
            url=url,
            status="success",
            file_hash=file_hash,
            file_size=file_size,
            duration_ms=duration_ms
        )
        self._save_event(event)
        logger.info(f"[审计] 下载成功: {product_code}, hash: {file_hash[:8]}...")
    
    def log_download_failed(self, product_code: str, url: str, 
                            error: str, retry_count: int = 0,
                            company: str = "未知",
                            product_name: Optional[str] = None):
        """记录下载失败"""
        event = AuditEvent(
            event_type=AuditEventType.DOWNLOAD_FAILED,
            timestamp=datetime.now(),
            company=company,
            product_code=product_code,
            product_name=product_name,
            url=url,
            status="failed",
            error_message=error,
            retry_count=retry_count
        )
        self._save_event(event)
        logger.error(f"[审计] 下载失败: {product_code}, 错误: {error}, 重试: {retry_count}")
    
    def log_download_retry(self, product_code: str, url: str, 
                           retry_count: int, error: str,
                           company: str = "未知"):
        """记录下载重试"""
        event = AuditEvent(
            event_type=AuditEventType.DOWNLOAD_RETRY,
            timestamp=datetime.now(),
            company=company,
            product_code=product_code,
            url=url,
            error_message=error,
            retry_count=retry_count
        )
        self._save_event(event)
        logger.warning(f"[审计] 下载重试: {product_code}, 第{retry_count}次, 原因: {error}")
    
    def log_rate_limited(self, url: str, company: str = "未知", 
                         wait_seconds: Optional[float] = None):
        """记录触发限流"""
        event = AuditEvent(
            event_type=AuditEventType.RATE_LIMITED,
            timestamp=datetime.now(),
            company=company,
            url=url,
            metadata={"wait_seconds": wait_seconds} if wait_seconds else {}
        )
        self._save_event(event)
        logger.warning(f"[审计] 触发限流: {url}, 等待: {wait_seconds}秒")
    
    def log_circuit_breaker(self, domain: str, cooldown_seconds: int,
                            trigger_reason: str = "429/403"):
        """记录触发熔断"""
        event = AuditEvent(
            event_type=AuditEventType.CIRCUIT_BREAKER,
            timestamp=datetime.now(),
            company=domain,  # 使用domain作为company字段
            url=domain,
            error_message=trigger_reason,
            metadata={"cooldown_seconds": cooldown_seconds}
        )
        self._save_event(event)
        logger.error(f"[审计] 触发熔断: {domain}, 冷却: {cooldown_seconds}秒, 原因: {trigger_reason}")
    
    def log_robots_blocked(self, url: str, company: str = "未知"):
        """记录被robots.txt阻止"""
        event = AuditEvent(
            event_type=AuditEventType.ROBOTS_BLOCKED,
            timestamp=datetime.now(),
            company=company,
            url=url,
            status="blocked"
        )
        self._save_event(event)
        logger.warning(f"[审计] robots.txt阻止: {url}")
    
    # ==================== 查询方法 ====================
    
    def query_events(
        self,
        event_type: Optional[AuditEventType] = None,
        company: Optional[str] = None,
        product_code: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """查询审计事件
        
        Args:
            event_type: 事件类型过滤
            company: 公司名称过滤
            product_code: 产品代码过滤
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制
            
        Returns:
            审计事件列表
        """
        conditions = []
        params = []
        
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type.value)
        if company:
            conditions.append("company LIKE ?")
            params.append(f"%{company}%")
        if product_code:
            conditions.append("product_code = ?")
            params.append(product_code)
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())
        
        query = "SELECT * FROM audit_events"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
        
        events = []
        for row in rows:
            event = AuditEvent(
                event_type=AuditEventType(row['event_type']),
                timestamp=datetime.fromisoformat(row['timestamp']),
                company=row['company'],
                product_code=row['product_code'],
                product_name=row['product_name'],
                url=row['url'],
                status=row['status'],
                file_hash=row['file_hash'],
                file_size=row['file_size'],
                error_message=row['error_message'],
                retry_count=row['retry_count'],
                duration_ms=row['duration_ms'],
                metadata=json.loads(row['metadata']) if row['metadata'] else {}
            )
            events.append(event)
        
        return events
    
    def get_statistics(self, company: Optional[str] = None,
                       start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """获取审计统计信息
        
        Args:
            company: 按公司过滤
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            统计信息字典
        """
        conditions = []
        params = []
        
        if company:
            conditions.append("company LIKE ?")
            params.append(f"%{company}%")
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())
        
        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
        
        with self._get_connection() as conn:
            # 统计各类事件数量
            cursor = conn.execute(f"""
                SELECT event_type, COUNT(*) as count
                FROM audit_events
                {where_clause}
                GROUP BY event_type
            """, params)
            event_counts = {row['event_type']: row['count'] for row in cursor.fetchall()}
            
            # 统计下载成功的文件总大小
            if conditions:
                cursor = conn.execute(f"""
                    SELECT SUM(file_size) as total_size
                    FROM audit_events
                    {where_clause} AND event_type = 'download_success'
                """, params)
            else:
                cursor = conn.execute("""
                    SELECT SUM(file_size) as total_size
                    FROM audit_events
                    WHERE event_type = 'download_success'
                """)
            total_size = cursor.fetchone()['total_size'] or 0
            
            # 统计公司分布
            cursor = conn.execute(f"""
                SELECT company, COUNT(*) as count
                FROM audit_events
                {where_clause}
                GROUP BY company
                ORDER BY count DESC
            """, params)
            company_counts = {row['company']: row['count'] for row in cursor.fetchall()}
        
        return {
            "event_counts": event_counts,
            "total_downloaded_size_bytes": total_size,
            "company_distribution": company_counts,
            "success_rate": self._calculate_success_rate(event_counts)
        }
    
    def _calculate_success_rate(self, event_counts: Dict[str, int]) -> float:
        """计算成功率"""
        success = event_counts.get('download_success', 0)
        failed = event_counts.get('download_failed', 0)
        total = success + failed
        return round(success / total * 100, 2) if total > 0 else 0.0
    
    def get_recent_failures(self, limit: int = 10) -> List[AuditEvent]:
        """获取最近的失败事件"""
        return self.query_events(
            event_type=AuditEventType.DOWNLOAD_FAILED,
            limit=limit
        )
    
    def get_download_history(self, product_code: str) -> List[AuditEvent]:
        """获取产品的下载历史"""
        return self.query_events(product_code=product_code, limit=50)


# 全局审计日志实例（单例模式）
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """获取全局审计日志实例"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
