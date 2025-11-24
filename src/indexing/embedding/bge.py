"""
BGE中文Embedding模型封装

使用BAAI/bge-small-zh-v1.5模型进行文本向量化
"""
from typing import List
from FlagEmbedding import FlagModel
from src.common.logging import logger


class BGEEmbedder:
    """BGE中文Embedding模型封装"""
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        batch_size: int = 32,
        device: str = "cpu"  # 或 "cuda" 如果有GPU
    ):
        """
        初始化BGE Embedder
        
        Args:
            model_name: 模型名称
            batch_size: 批处理大小
            device: 运行设备 (cpu/cuda)
        """
        logger.info(f"Loading BGE model: {model_name}")
        
        # 加载模型 (首次运行会自动下载)
        self.model = FlagModel(
            model_name,
            query_instruction_for_retrieval="为这个句子生成表示以用于检索相关文章：",
            use_fp16=False  # CPU模式使用FP32
        )
        
        self.batch_size = batch_size
        self.device = device
        self.total_tokens = 0
        
        logger.info(f"BGE model loaded on {device}")
    
    def embed_single(self, text: str) -> List[float]:
        """
        生成单个文本的embedding
        
        Args:
            text: 输入文本
            
        Returns:
            512维向量
        """
        # BGE使用encode方法
        embedding = self.model.encode(text)
        
        # 估算token数 (中文约1.5字符=1token)
        self.total_tokens += len(text) // 1.5
        
        return embedding.tolist()
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成embedding
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表
        """
        embeddings = self.model.encode(texts, batch_size=self.batch_size)
        
        # 估算token数
        total_chars = sum(len(t) for t in texts)
        self.total_tokens += total_chars // 1.5
        
        return embeddings.tolist()
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total_tokens": int(self.total_tokens),
            "estimated_cost_usd": 0.0,  # 本地模型,成本为0
            "model_name": "BAAI/bge-small-zh-v1.5",
            "vector_dimension": 512
        }


def get_embedder(batch_size: int = 32, device: str = "cpu"):
    """
    获取BGE Embedder实例
    
    Args:
        batch_size: 批处理大小
        device: 运行设备
        
    Returns:
        BGEEmbedder实例
    """
    return BGEEmbedder(batch_size=batch_size, device=device)
