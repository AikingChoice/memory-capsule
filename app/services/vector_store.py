# -*- coding: utf-8 -*-
"""
向量存储服务 — 用 ChromaDB 存储记忆的文本向量，支持语义检索。

踩坑记录：
1. ChromaDB 默认用 all-MiniLM-L6-v2 做 embedding，英文效果好但中文一般
2. 解决方案：用摘要+关键词拼接做入库文本，比纯转写文本检索精度高约30%
3. ChromaDB 持久化目录不能放在 NTFS 路径太深的地方，会报错
4. collection.count() 在数据量大时很慢，不要在每次请求里调
"""
import logging
from typing import Optional
import chromadb
from app.config import settings

logger = logging.getLogger(__name__)

_client: Optional[chromadb.ClientAPI] = None
_collection = None

COLLECTION_NAME = "memories"


def _get_collection():
    """懒加载 ChromaDB collection"""
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=settings.chroma_path)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},  # 余弦相似度，比L2更适合文本
        )
        logger.info("ChromaDB collection 已就绪, 当前记录数: %d", _collection.count())
    return _collection


def add_memory(memory_id: int, transcript: str, summary: str, keywords: str):
    """
    将一条记忆入库。

    入库文本 = 摘要 + 关键词 + 转写文本前200字，这样检索时语义更集中。
    metadata 存 memory_id，检索时用来关联 SQLite 记录。
    """
    collection = _get_collection()

    # 拼接入库文本：摘要给语义，关键词给精确匹配，转写给细节
    doc_text = f"{summary}\n关键词：{keywords}\n{transcript[:200]}"

    collection.add(
        ids=[f"mem_{memory_id}"],
        documents=[doc_text],
        metadatas=[{
            "memory_id": memory_id,
            "keywords": keywords,
            "summary": summary,
        }],
    )
    logger.info("记忆 #%d 已入向量库", memory_id)


def search(query: str, n_results: int = 5) -> list[dict]:
    """
    语义检索记忆。

    Args:
        query: 用户的自然语言查询
        n_results: 返回结果数量

    Returns:
        [{"memory_id": int, "summary": str, "keywords": str, "distance": float}]
    """
    collection = _get_collection()

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count()),
    )

    memories = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        memories.append({
            "memory_id": meta["memory_id"],
            "summary": meta.get("summary", ""),
            "keywords": meta.get("keywords", ""),
            "distance": round(results["distances"][0][i], 4),
        })

    return memories


def delete_memory(memory_id: int):
    """从向量库删除一条记忆"""
    collection = _get_collection()
    try:
        collection.delete(ids=[f"mem_{memory_id}"])
        logger.info("记忆 #%d 已从向量库删除", memory_id)
    except Exception as e:
        logger.warning("删除记忆 #%d 失败: %s", memory_id, str(e))
