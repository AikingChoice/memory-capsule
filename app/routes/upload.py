# -*- coding: utf-8 -*-
"""
音频上传和处理路由。

处理流程：上传音频→保存文件→创建数据库记录→后台任务执行转写+分析+入库。
用后台线程处理，不阻塞接口返回。
"""
import logging
import os
import uuid
from pathlib import Path
from threading import Thread

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models import get_db, Memory
from app.services.transcriber import transcribe
from app.services.analyzer import analyze
from app.services.vector_store import add_memory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/upload", tags=["upload"])

UPLOAD_DIR = Path("./data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _process_memory(memory_id: int, audio_path: str):
    """
    后台处理任务：转写→分析→入向量库。

    这个函数在独立线程里跑，即使出错也不会影响主进程。
    遇到异常时更新数据库状态为 failed，方便前端展示错误。
    """
    from app.models import SessionLocal
    db = SessionLocal()

    try:
        memory = db.query(Memory).filter(Memory.id == memory_id).first()
        if not memory:
            return

        # Step 1: 转写
        memory.status = "processing"
        db.commit()
        logger.info("开始处理记忆 #%d", memory_id)

        result = transcribe(audio_path)
        memory.transcript = result["text"]
        memory.duration_seconds = result["duration"]

        # Step 2: AI 分析
        analysis = analyze(result["text"])
        memory.summary = analysis["summary"]
        memory.keywords = analysis["keywords"]
        memory.sentiment = analysis["sentiment"]
        memory.sentiment_reason = analysis["sentiment_reason"]

        # Step 3: 入向量库
        add_memory(
            memory_id=memory_id,
            transcript=result["text"],
            summary=analysis["summary"],
            keywords=analysis["keywords"],
        )

        memory.status = "done"
        db.commit()
        logger.info("记忆 #%d 处理完成", memory_id)

    except Exception as e:
        logger.error("记忆 #%d 处理失败: %s", memory_id, str(e))
        memory = db.query(Memory).filter(Memory.id == memory_id).first()
        if memory:
            memory.status = "failed"
            memory.error_message = str(e)
            db.commit()
    finally:
        db.close()


@router.post("")
async def upload_audio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    上传音频文件。

    支持格式：mp3, wav, m4a, webm, ogg, flac
    返回记忆 ID，前端用这个 ID 轮询处理状态。
    """
    # 校验文件类型
    allowed_ext = {".mp3", ".wav", ".m4a", ".webm", ".ogg", ".flac"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_ext:
        raise HTTPException(400, f"不支持的音频格式: {ext}，支持: {', '.join(allowed_ext)}")

    # 保存文件
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / filename

    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > settings.max_audio_size_mb:
        raise HTTPException(400, f"文件过大: {file_size_mb:.1f}MB，最大 {settings.max_audio_size_mb}MB")

    with open(file_path, "wb") as f:
        f.write(content)

    # 创建数据库记录
    memory = Memory(
        audio_path=str(file_path),
        transcript="",
        status="pending",
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)

    # 启动后台处理线程
    thread = Thread(target=_process_memory, args=(memory.id, str(file_path)), daemon=True)
    thread.start()

    logger.info("音频已上传: %s -> 记忆 #%d", file.filename, memory.id)

    return {
        "id": memory.id,
        "status": "pending",
        "message": "音频已上传，正在处理中...",
    }
