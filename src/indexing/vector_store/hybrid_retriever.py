"""混合检索器：Dense Vector + BM25

结合语义检索（Dense Vector）和关键词检索（BM25），使用RRF算法融合结果。

核心组件：
1. BM25Index: 基于rank-bm25的关键词索引
2. HybridRetriever: 混合检索器（Dense + Sparse + RRF）
3. RRF算法: Reciprocal Rank Fusion

根据 spec.md §FR-011 和 tasks.md §T022a 实施。
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging

import jieba
from rank_bm25 import BM25Okapi

from src.indexing.vector_store.chroma import ChromaDBStore
from src.common.models import PolicyChunk

logger = logging.getLogger(__name__)


class BM25Index:
    """BM25关键词索引
    
    使用jieba分词和rank-bm25实现中文关键词检索。
    
    特性：
    - 中文分词（jieba）
    - BM25Okapi算法
    - 增量更新支持
    - 持久化（可选）
    """
    
    def __init__(self):
        """初始化BM25索引"""
        self.corpus = []  # 原始文本列表
        self.tokenized_corpus = []  # 分词后的文本列表
        self.chunk_ids = []  # chunk ID列表（与corpus对应）
        self.bm25 = None
        
        # 停用词（可扩展）
        self.stopwords = set([
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人',
            '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
            '你', '会', '着', '没有', '看', '好', '自己', '这'
        ])
        
        logger.info("初始化BM25索引")
    
    def _tokenize(self, text: str) -> List[str]:
        """中文分词
        
        Args:
            text: 输入文本
        
        Returns:
            分词结果（去除停用词）
        """
        # jieba分词
        tokens = jieba.cut(text)
        
        # 过滤停用词和单字符
        filtered_tokens = [
            token for token in tokens
            if len(token) > 1 and token not in self.stopwords
        ]
        
        return filtered_tokens
    
    def build(self, chunks: List[PolicyChunk]):
        """构建BM25索引
        
        Args:
            chunks: PolicyChunk列表
        """
        logger.info(f"构建BM25索引，文档数={len(chunks)}...")
        
        self.corpus = [chunk.content for chunk in chunks]
        self.chunk_ids = [chunk.id for chunk in chunks]
        
        # 分词
        self.tokenized_corpus = [self._tokenize(text) for text in self.corpus]
        
        # 构建BM25索引
        self.bm25 = BM25Okapi(self.tokenized_corpus)
        
        logger.info(f"BM25索引构建完成，索引 {len(self.corpus)} 个文档")
    
    def add_chunk(self, chunk: PolicyChunk):
        """增量添加chunk（注意：需要重建索引）
        
        Args:
            chunk: PolicyChunk对象
        """
        self.corpus.append(chunk.content)
        self.chunk_ids.append(chunk.id)
        self.tokenized_corpus.append(self._tokenize(chunk.content))
        
        # 重建索引（BM25Okapi不支持真正的增量更新）
        self.bm25 = BM25Okapi(self.tokenized_corpus)
        
        logger.debug(f"添加chunk {chunk.id[:8]}... 并重建索引")
    
    def search(self, query: str, n_results: int = 10) -> List[Tuple[str, float]]:
        """BM25检索
        
        Args:
            query: 查询字符串
            n_results: 返回结果数量
        
        Returns:
            [(chunk_id, score), ...] 列表，按score降序排列
        """
        if not self.bm25:
            logger.warning("BM25索引未构建，返回空结果")
            return []
        
        # 分词查询
        tokenized_query = self._tokenize(query)
        
        if not tokenized_query:
            logger.warning(f"查询分词后为空: {query}")
            return []
        
        # BM25检索
        scores = self.bm25.get_scores(tokenized_query)
        
        # 获取Top-K
        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:n_results]
        
        results = [
            (self.chunk_ids[i], float(scores[i]))
            for i in top_indices
            if scores[i] > 0  # 过滤零分结果
        ]
        
        logger.debug(f"BM25检索到 {len(results)} 个结果，查询='{query[:30]}...'")
        
        return results
    
    def save(self, path: str):
        """保存索引到文件
        
        Args:
            path: 保存路径
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'corpus': self.corpus,
            'chunk_ids': self.chunk_ids,
            'tokenized_corpus': self.tokenized_corpus
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"BM25索引已保存到 {path}")
    
    def load(self, path: Optional[str] = None):
        """从文件加载索引
        
        Args:
            path: 文件路径（可选，默认使用config.BM25_INDEX_PATH）
        """
        if path is None:
            from src.common.config import config
            path = config.BM25_INDEX_PATH
        
        path = Path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"索引文件不存在: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.corpus = data['corpus']
        self.chunk_ids = data['chunk_ids']
        self.tokenized_corpus = data['tokenized_corpus']
        
        # 重建BM25索引
        self.bm25 = BM25Okapi(self.tokenized_corpus)
        
        logger.info(f"从 {path} 加载BM25索引，文档数={len(self.corpus)}")


class HybridRetriever:
    """混合检索器
    
    结合Dense Vector（语义）和BM25（关键词），使用RRF算法融合结果。
    
    检索策略：
    - 数字查询（如"保险期间90天"）：80% BM25 + 20% Vector
    - 自然语言查询（如"保险期间多久"）：20% BM25 + 80% Vector
    
    RRF算法：
    - score(chunk) = sum(1 / (k + rank_i))
    - k=60（默认值）
    """
    
    def __init__(
        self,
        chroma_store: ChromaDBStore,
        bm25_index: BM25Index,
        default_bm25_weight: float = 0.5,
        default_vector_weight: float = 0.5,
        rrf_k: int = 20  # 降低k值增强BM25影响力
    ):
        """初始化混合检索器
        
        Args:
            chroma_store: ChromaDB存储实例
            bm25_index: BM25索引实例
            default_bm25_weight: BM25权重（默认0.5）
            default_vector_weight: Vector权重（默认0.5）
            rrf_k: RRF算法的k参数
        """
        self.chroma_store = chroma_store
        self.bm25_index = bm25_index
        self.default_bm25_weight = default_bm25_weight
        self.default_vector_weight = default_vector_weight
        self.rrf_k = rrf_k
        
        logger.info(f"初始化混合检索器，BM25权重={default_bm25_weight}，Vector权重={default_vector_weight}，RRF_k={rrf_k}")
    
    def _detect_query_type(self, query: str) -> str:
        """检测查询类型
        
        Args:
            query: 查询字符串
        
        Returns:
            'exclusion' (免责) / 'rate_table' (费率) / 'numeric' (数字) / 'natural' (自然语言)
        """
        query_lower = query.lower()
        
        # 1. 免责查询检测
        exclusion_keywords = ["不赔", "免责", "除外", "不予理赔", "赔吗", "会赔", "能赔", 
                             "醉酒", "酒驾", "酒后", "自杀", "吸毒", "犯罪", "战争"]
        if any(kw in query_lower for kw in exclusion_keywords):
            logger.debug(f"检测到免责查询: {query}")
            return 'exclusion'
        
        # 2. 费率查询检测
        rate_keywords = ["保费", "费率", "多少钱", "价格", "费用", "交多少", "投保费用"]
        has_number = any(char.isdigit() for char in query)
        if any(kw in query_lower for kw in rate_keywords):
            logger.debug(f"检测到费率查询: {query}")
            return 'rate_table'
        
        # 3. 数字查询检测
        numeric_indicators = ['%', '元', '万元', '天', '年', '月', '日', '岁']
        has_indicator = any(ind in query for ind in numeric_indicators)
        
        if has_number or has_indicator:
            return 'numeric'
        
        return 'natural'
    
    def search(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        auto_weight: bool = True
    ) -> List[Dict[str, Any]]:
        """混合检索
        
        Args:
            query: 查询字符串
            query_embedding: 查询向量（可选，如果提供则跳过embedding生成）
            n_results: 返回结果数量
            where: metadata过滤条件（仅应用于Vector检索）
            auto_weight: 是否根据查询类型自动调整权重
        
        Returns:
            结果列表，每个结果包含：
            - id: chunk ID
            - document: chunk内容
            - metadata: chunk元数据
            - rrf_score: RRF融合分数
            - dense_rank: Vector检索排名（1-based）
            - sparse_rank: BM25检索排名（1-based）
        
        Example:
            >>> retriever.search("保险期间90天", n_results=5)
            >>> retriever.search("什么情况不赔", where={"category": "Exclusion"})
        """
        # 1. 自动调整权重
        bm25_weight = self.default_bm25_weight
        vector_weight = self.default_vector_weight
        
        if auto_weight:
            query_type = self._detect_query_type(query)
            
            if query_type == 'exclusion':
                # 免责查询: 关键词匹配很重要("酒驾"/"醉酒")
                bm25_weight = 0.65
                vector_weight = 0.35
                logger.debug(f"免责查询，BM25=0.65，Vector=0.35")
                
            elif query_type == 'rate_table':
                # 费率查询: 关键词+数字精确匹配重要
                bm25_weight = 0.7
                vector_weight = 0.3
                logger.debug(f"费率查询，BM25=0.7，Vector=0.3")
                
            elif query_type == 'numeric':
                bm25_weight = 0.8
                vector_weight = 0.2
                logger.debug(f"数字查询，BM25=0.8，Vector=0.2")
            else:
                bm25_weight = 0.2
                vector_weight = 0.8
                logger.debug(f"自然语言查询，BM25=0.2，Vector=0.8")
        
        # 2. BM25检索
        bm25_results = self.bm25_index.search(query, n_results=n_results * 2)
        bm25_ranks = {chunk_id: rank + 1 for rank, (chunk_id, _) in enumerate(bm25_results)}
        
        # 3. Vector检索
        if query_embedding is None:
            # 如果没有提供embedding，需要生成（这里假设外部已生成）
            raise ValueError("必须提供query_embedding参数")
        
        vector_results = self.chroma_store.search(
            query_embedding=query_embedding,
            n_results=n_results * 2,
            where=where
        )
        vector_ranks = {result['id']: rank + 1 for rank, result in enumerate(vector_results)}
        
        # 4. RRF融合
        rrf_scores = self._compute_rrf_scores(
            bm25_ranks,
            vector_ranks,
            bm25_weight,
            vector_weight
        )
        
        # 5. 排序并获取Top-K
        sorted_chunk_ids = sorted(
            rrf_scores.keys(),
            key=lambda cid: rrf_scores[cid],
            reverse=True
        )[:n_results]
        
        # 6. 构建最终结果
        # 创建chunk_id到vector result的映射
        vector_result_map = {result['id']: result for result in vector_results}
        
        final_results = []
        for chunk_id in sorted_chunk_ids:
            # 从ChromaDB获取完整信息
            if chunk_id in vector_result_map:
                result = vector_result_map[chunk_id]
                result['rrf_score'] = rrf_scores[chunk_id]
                result['dense_rank'] = vector_ranks.get(chunk_id, None)
                result['sparse_rank'] = bm25_ranks.get(chunk_id, None)
                final_results.append(result)
            else:
                # 如果只在BM25中出现，需要从ChromaDB获取
                chunk = self.chroma_store.get_chunk(chunk_id)
                if chunk:
                    final_results.append({
                        'id': chunk.id,
                        'document': chunk.content,
                        'metadata': chunk.to_chroma_metadata(),
                        'distance': None,
                        'rrf_score': rrf_scores[chunk_id],
                        'dense_rank': vector_ranks.get(chunk_id, None),
                        'sparse_rank': bm25_ranks.get(chunk_id, None)
                    })
        
        logger.info(f"混合检索完成，返回 {len(final_results)} 个结果")
        
        return final_results
    
    def _compute_rrf_scores(
        self,
        bm25_ranks: Dict[str, int],
        vector_ranks: Dict[str, int],
        bm25_weight: float,
        vector_weight: float
    ) -> Dict[str, float]:
        """计算RRF分数
        
        RRF公式：score = w1 * 1/(k + rank1) + w2 * 1/(k + rank2)
        
        Args:
            bm25_ranks: {chunk_id: rank} BM25排名（1-based）
            vector_ranks: {chunk_id: rank} Vector排名（1-based）
            bm25_weight: BM25权重
            vector_weight: Vector权重
        
        Returns:
            {chunk_id: rrf_score}
        """
        # 合并所有chunk_id
        all_chunk_ids = set(bm25_ranks.keys()) | set(vector_ranks.keys())
        
        rrf_scores = {}
        for chunk_id in all_chunk_ids:
            score = 0.0
            
            # BM25贡献
            if chunk_id in bm25_ranks:
                score += bm25_weight * (1.0 / (self.rrf_k + bm25_ranks[chunk_id]))
            
            # Vector贡献
            if chunk_id in vector_ranks:
                score += vector_weight * (1.0 / (self.rrf_k + vector_ranks[chunk_id]))
            
            rrf_scores[chunk_id] = score
        
        return rrf_scores


def create_hybrid_retriever(
    chroma_store: ChromaDBStore,
    bm25_index: Optional[BM25Index] = None,
    chunks: Optional[List[PolicyChunk]] = None
) -> HybridRetriever:
    """工厂函数：创建混合检索器
    
    Args:
        chroma_store: ChromaDB存储实例
        bm25_index: BM25索引实例（可选，如果不提供则从chunks构建）
        chunks: PolicyChunk列表（用于构建BM25索引）
    
    Returns:
        HybridRetriever实例
    """
    if bm25_index is None:
        if chunks is None:
            raise ValueError("必须提供bm25_index或chunks参数")
        
        bm25_index = BM25Index()
        bm25_index.build(chunks)
    
    return HybridRetriever(
        chroma_store=chroma_store,
        bm25_index=bm25_index
    )

