# -*- coding: utf-8 -*-
"""
记忆管理路由 — 查询、列表、删除记忆。
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models import get_db, Memory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memories", tags=["memories"])


@router.get("")
def list_memories(
    page: int = 1,
    size: int = 20,
    sentiment: str = None,
    db: Session = Depends(get_db),
):
    """
    记忆列表，支持分页和情绪筛选。
    """
    query = db.query(Memory).filter(Memory.status == "done")

    if sentiment and sentiment in ("positive", "neutral", "negative"):
        query = query.filter(Memory.sentiment == sentiment)

    total = query.count()
    memories = query.order_by(Memory.created_at.desc()).offset((page - 1) * size).limit(size).all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [_memory_to_dict(m) for m in memories],
    }


@router.get("/{memory_id}")
def get_memory(memory_id: int, db: Session = Depends(get_db)):
    """获取单条记忆详情"""
    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory:
        raise HTTPException(404, "记忆不存在")
    return _memory_to_dict(memory)


@router.delete("/{memory_id}")
def delete_memory(memory_id: int, db: Session = Depends(get_db)):
    """删除一条记忆（同时删除向量库中的记录）"""
    from app.services.vector_store import delete_memory as vs_delete

    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory:
        raise HTTPException(404, "记忆不存在")

    # 删除向量库记录
    vs_delete(memory_id)

    # 删除音频文件
    import os
    if memory.audio_path and os.path.exists(memory.audio_path):
        os.remove(memory.audio_path)

    # 删除数据库记录
    db.delete(memory)
    db.commit()

    logger.info("记忆 #%d 已删除", memory_id)
    return {"message": "已删除"}


@router.get("/stats/overview")
def stats_overview(db: Session = Depends(get_db)):
    """统计数据概览"""
    total = db.query(Memory).filter(Memory.status == "done").count()
    positive = db.query(Memory).filter(Memory.status == "done", Memory.sentiment == "positive").count()
    neutral = db.query(Memory).filter(Memory.status == "done", Memory.sentiment == "neutral").count()
    negative = db.query(Memory).filter(Memory.status == "done", Memory.sentiment == "negative").count()

    return {
        "total": total,
        "sentiment": {
            "positive": positive,
            "neutral": neutral,
            "negative": negative,
        },
    }


def _memory_to_dict(m: Memory) -> dict:
    return {
        "id": m.id,
        "transcript": m.transcript,
        "summary": m.summary,
        "keywords": m.keywords,
        "sentiment": m.sentiment,
        "sentiment_reason": m.sentiment_reason,
        "duration_seconds": m.duration_seconds,
        "status": m.status,
        "error_message": m.error_message,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }
