# -*- coding: utf-8 -*-
"""
对话回忆路由 — 用户提问，检索相关记忆并生成回答。
"""
import logging
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.recall import recall

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    对话接口：用户提问，系统检索相关记忆并生成自然语言回答。
    """
    if not req.question.strip():
        return ChatResponse(answer="请输入你的问题", sources=[])

    logger.info("收到提问: %s", req.question[:50])
    result = recall(req.question)
    return ChatResponse(answer=result["answer"], sources=result["sources"])
