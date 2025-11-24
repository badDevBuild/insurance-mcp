"""OpenAI Embedding包装器

提供OpenAI text-embedding-3-small模型的封装，支持：
- 批量embedding生成
- 错误处理和重试机制
- Token计数和成本估算

根据 tasks.md §T021 实施。
"""
import time
from typing import List, Dict, Any, Optional
import logging
from openai import OpenAI, RateLimitError, APIError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from src.common.config import config

logger = logging.getLogger(__name__)


class OpenAIEmbedder:
    """OpenAI Embedding生成器
    
    使用text-embedding-3-small模型生成向量embeddings。
    
    特性：
    - 自动批处理（默认100个文本/批）
    - 指数退避重试（最多3次）
    - Token计数和成本估算
    - 错误处理和日志记录
    """
    
    # 模型配置
    MODEL = "text-embedding-3-small"
    DIMENSION = 1536  # 输出维度
    MAX_TOKENS = 8191  # 每个文本的最大token数
    BATCH_SIZE = 100  # 每批处理的文本数
    
    # 成本估算（美元/1000 tokens）
    COST_PER_1K_TOKENS = 0.00002
    
    def __init__(self, api_key: Optional[str] = None, batch_size: int = 100):
        """初始化OpenAI客户端
        
        Args:
            api_key: OpenAI API密钥（可选，从配置读取）
            batch_size: 每批处理的文本数量
        """
        self.api_key = api_key or config.OPENAI_API_KEY
        
        if not self.api_key:
            raise ValueError("未设置OPENAI_API_KEY，请在.env文件中配置")
        
        self.client = OpenAI(api_key=self.api_key)
        self.batch_size = batch_size
        
        # 统计信息
        self.total_tokens_used = 0
        self.total_requests = 0
        
        logger.info(f"初始化OpenAI Embedder，模型={self.MODEL}，批大小={self.batch_size}")
    
    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _create_embedding(self, texts: List[str]) -> List[List[float]]:
        """调用OpenAI API生成embeddings（带重试）
        
        Args:
            texts: 文本列表
        
        Returns:
            嵌入向量列表
        
        Raises:
            RateLimitError: API速率限制
            APIError: API错误
        """
        response = self.client.embeddings.create(
            model=self.MODEL,
            input=texts,
            encoding_format="float"
        )
        
        # 更新统计信息
        self.total_tokens_used += response.usage.total_tokens
        self.total_requests += 1
        
        # 提取向量
        embeddings = [item.embedding for item in response.data]
        
        logger.debug(f"生成 {len(embeddings)} 个embeddings，使用 {response.usage.total_tokens} tokens")
        
        return embeddings
    
    def embed_single(self, text: str) -> List[float]:
        """生成单个文本的embedding
        
        Args:
            text: 输入文本
        
        Returns:
            1536维向量
        
        Raises:
            ValueError: 文本为空
            RateLimitError: API速率限制
        """
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        
        # 截断过长的文本
        text = self._truncate_text(text)
        
        try:
            embeddings = self._create_embedding([text])
            return embeddings[0]
        except RateLimitError as e:
            logger.error(f"OpenAI API速率限制: {e}")
            raise
        except APIError as e:
            logger.error(f"OpenAI API错误: {e}")
            raise
        except Exception as e:
            logger.error(f"生成embedding失败: {e}")
            raise
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成embeddings
        
        Args:
            texts: 文本列表
        
        Returns:
            向量列表，与输入文本一一对应
        
        Raises:
            ValueError: 文本列表为空
        """
        if not texts:
            raise ValueError("文本列表不能为空")
        
        # 过滤空文本并截断
        valid_texts = []
        valid_indices = []
        
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(self._truncate_text(text))
                valid_indices.append(i)
        
        if not valid_texts:
            raise ValueError("所有文本都为空")
        
        logger.info(f"批量生成 {len(valid_texts)} 个embeddings...")
        
        # 分批处理
        all_embeddings = []
        for i in range(0, len(valid_texts), self.batch_size):
            batch = valid_texts[i:i + self.batch_size]
            
            try:
                batch_embeddings = self._create_embedding(batch)
                all_embeddings.extend(batch_embeddings)
                
                # 避免过快请求
                if i + self.batch_size < len(valid_texts):
                    time.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"批次 {i//self.batch_size + 1} 失败: {e}")
                raise
        
        # 构建完整结果（包含None for 空文本）
        result = [None] * len(texts)
        for idx, embedding in zip(valid_indices, all_embeddings):
            result[idx] = embedding
        
        logger.info(f"成功生成 {len(all_embeddings)} 个embeddings")
        
        return result
    
    def _truncate_text(self, text: str) -> str:
        """截断过长的文本
        
        简化版：按字符数估算（1 token ≈ 4 字符）
        更精确的方法应使用tiktoken库
        
        Args:
            text: 输入文本
        
        Returns:
            截断后的文本
        """
        max_chars = self.MAX_TOKENS * 4
        
        if len(text) > max_chars:
            logger.warning(f"文本过长（{len(text)}字符），截断至{max_chars}字符")
            return text[:max_chars]
        
        return text
    
    def get_stats(self) -> Dict[str, Any]:
        """获取使用统计
        
        Returns:
            统计信息字典
        """
        estimated_cost = (self.total_tokens_used / 1000.0) * self.COST_PER_1K_TOKENS
        
        return {
            'total_requests': self.total_requests,
            'total_tokens': self.total_tokens_used,
            'estimated_cost_usd': round(estimated_cost, 6),
            'model': self.MODEL,
            'dimension': self.DIMENSION
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.total_tokens_used = 0
        self.total_requests = 0
        logger.info("统计信息已重置")


def get_embedder(batch_size: int = 100) -> OpenAIEmbedder:
    """工厂函数：获取OpenAI Embedder实例
    
    Args:
        batch_size: 批处理大小
    
    Returns:
        OpenAIEmbedder实例
    """
    return OpenAIEmbedder(batch_size=batch_size)


# 便捷函数
def embed_text(text: str) -> List[float]:
    """便捷函数：生成单个文本的embedding
    
    Args:
        text: 输入文本
    
    Returns:
        1536维向量
    """
    embedder = get_embedder()
    return embedder.embed_single(text)


def embed_texts(texts: List[str], batch_size: int = 100) -> List[List[float]]:
    """便捷函数：批量生成embeddings
    
    Args:
        texts: 文本列表
        batch_size: 批处理大小
    
    Returns:
        向量列表
    """
    embedder = get_embedder(batch_size=batch_size)
    return embedder.embed_batch(texts)

