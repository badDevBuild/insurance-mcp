"""
LLM解析文档测试索引器

独立的索引器，用于测试LLM解析的Markdown文档
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import uuid
from datetime import datetime
from typing import List, Dict, Any

from tests.llm_parsed_test.config import (
    LLM_PARSED_DOCS,
    TEST_PRODUCT,
    TEST_VECTOR_STORE_DIR,
    TEST_BM25_INDEX_PATH,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    CHROMA_COLLECTION_NAME,
    ensure_test_dirs
)
from tests.llm_parsed_test.chunking_strategy import create_table_aware_chunker
from src.common.models import PolicyChunk
from src.indexing.embedding.bge import BGEEmbedder
from src.indexing.vector_store.chroma import ChromaDBStore
from src.indexing.vector_store.hybrid_retriever import BM25Index
from src.common.logging import logger


class LLMTestIndexer:
    """LLM解析文档测试索引器"""
    
    def __init__(self):
        ensure_test_dirs()
        
        self.chunker = create_table_aware_chunker(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP
        )
        self.embedder = BGEEmbedder()
        self.chroma_store = ChromaDBStore(
            persist_directory=str(TEST_VECTOR_STORE_DIR)
        )
        self.bm25_index = BM25Index()
        
        logger.info(f"LLMTestIndexer initialized")
        logger.info(f"Vector store: {TEST_VECTOR_STORE_DIR}")
        logger.info(f"Collection: {CHROMA_COLLECTION_NAME}")
    
    def index_all_documents(self) -> Dict[str, Any]:
        """索引所有LLM解析的文档"""
        logger.info("=" * 80)
        logger.info("开始索引LLM解析的文档")
        logger.info("=" * 80)
        
        stats = {
            'total_documents': len(LLM_PARSED_DOCS),
            'total_chunks': 0,
            'success': 0,
            'failed': 0,
            'doc_stats': []
        }
        
        for doc_type, md_path in LLM_PARSED_DOCS.items():
            logger.info(f"\n处理文档: {doc_type} ({md_path.name})")
            
            if not md_path.exists():
                logger.error(f"文件不存在: {md_path}")
                stats['failed'] += 1
                continue
            
            try:
                # 读取Markdown
                with open(md_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
                
                logger.info(f"文件大小: {len(markdown_content)} 字符")
                
                # 使用LLM专用chunker分块
                chunk_dicts = self.chunker.chunk_with_hierarchy(
                    markdown=markdown_content,
                    doc_id=f"llm-test-{doc_type}",
                    doc_type=doc_type
                )
                
                logger.info(f"生成了 {len(chunk_dicts)} 个chunks")
                
                # 转换为PolicyChunk对象
                chunks = self._create_policy_chunks(chunk_dicts, doc_type)
                
                # 生成embeddings
                chunks = self._generate_embeddings(chunks)
                
                # 保存到ChromaDB
                self.chroma_store.add_chunks(chunks)
                
                # 更新BM25索引
                for chunk in chunks:
                    self.bm25_index.add_chunk(chunk)
                
                stats['total_chunks'] += len(chunks)
                stats['success'] += 1
                stats['doc_stats'].append({
                    'doc_type': doc_type,
                    'chunks': len(chunks),
                    'file': md_path.name
                })
                
                logger.info(f"✅ {doc_type}: {len(chunks)} chunks indexed")
                
            except Exception as e:
                logger.error(f"索引 {doc_type} 失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                stats['failed'] += 1
        
        # 保存BM25索引
        try:
            self.bm25_index.save(str(TEST_BM25_INDEX_PATH))
            logger.info(f"\nBM25索引已保存: {TEST_BM25_INDEX_PATH}")
        except Exception as e:
            logger.error(f"保存BM25索引失败: {e}")
        
        # 打印总结
        logger.info("\n" + "=" * 80)
        logger.info("索引完成!")
        logger.info("=" * 80)
        logger.info(f"成功文档: {stats['success']}/{stats['total_documents']}")
        logger.info(f"总chunks: {stats['total_chunks']}")
        logger.info(f"失败: {stats['failed']}")
        
        for doc_stat in stats['doc_stats']:
            logger.info(f"  - {doc_stat['doc_type']}: {doc_stat['chunks']} chunks")
        
        logger.info("=" * 80)
        
        return stats
    
    def _create_policy_chunks(self, chunk_dicts: List[Dict], doc_type: str) -> List[PolicyChunk]:
        """将chunk字典转为PolicyChunk对象"""
        chunks = []
        
        for chunk_dict in chunk_dicts:
            chunk = PolicyChunk(
                id=str(uuid.uuid4()),
                document_id=f"llm-test-{doc_type}",
                company=TEST_PRODUCT['company'],
                product_code=TEST_PRODUCT['product_code'],
                product_name=TEST_PRODUCT['name'],
                doc_type=doc_type,
                content=chunk_dict['content'],
                section_id=chunk_dict.get('section_id', ''),
                section_title=chunk_dict.get('section_title', ''),
                section_path=chunk_dict.get('section_path', ''),
                level=chunk_dict.get('level', 1),
                chunk_index=chunk_dict.get('chunk_index', 0),
                category=chunk_dict.get('category', 'General'),
                table_refs=[],
                entity_role='Insured',  # 默认值，符合枚举要求
                keywords=[],  # 必须是列表
                created_at=datetime.now()
            )
            chunks.append(chunk)
        
        return chunks
    
    def _generate_embeddings(self, chunks: List[PolicyChunk]) -> List[PolicyChunk]:
        """批量生成embeddings"""
        logger.info("生成embeddings...")
        
        contents = [chunk.content for chunk in chunks]
        embeddings = self.embedder.embed_batch(contents)
        
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding_vector = embedding
        
        stats = self.embedder.get_stats()
        logger.info(f"Embeddings生成完成: {stats['total_tokens']} tokens")
        
        return chunks
    
    def reset(self):
        """重置测试环境"""
        logger.warning("重置测试环境...")
        self.chroma_store.reset()
        self.bm25_index = BM25Index()
        logger.info("测试环境已重置")


def main():
    """主函数"""
    import argparse
    from src.common.logging import setup_logging
    
    parser = argparse.ArgumentParser(description="LLM解析文档测试索引器")
    parser.add_argument('--rebuild', action='store_true', help="重建索引（清空现有数据）")
    
    args = parser.parse_args()
    
    setup_logging()
    
    indexer = LLMTestIndexer()
    
    if args.rebuild:
        indexer.reset()
    
    stats = indexer.index_all_documents()
    
    # 打印ChromaDB统计
    chroma_stats = indexer.chroma_store.get_stats()
    print(f"\n📊 ChromaDB统计:")
    print(f"  - Collection: {chroma_stats['collection_name']}")
    print(f"  - Total chunks: {chroma_stats['total_chunks']}")
    print(f"  - Vector dimension: {chroma_stats['vector_dimension']}")
    print(f"  - Distance metric: {chroma_stats['distance_metric']}")
    
    if stats['success'] == stats['total_documents']:
        print(f"\n✅ 所有文档索引成功!")
    else:
        print(f"\n⚠️ {stats['failed']} 个文档索引失败")


if __name__ == "__main__":
    main()
