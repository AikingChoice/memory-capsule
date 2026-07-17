# -*- coding: utf-8 -*-
"""
对话回忆服务 — 用户提问→检索相关记忆→LLM 生成自然语言回答。

设计思路：
1. 先用向量检索找到最相关的 3-5 条记忆
2. 把这些记忆的摘要和原文拼成 context
3. 让 LLM 基于 context 回答用户问题
4. 如果没有相关记忆，直接告诉用户"没有找到相关回忆"
"""
import logging
from openai import OpenAI
from app.config import settings
from app.services import vector_store
from app.models import SessionLocal, Memory

logger = logging.getLogger(__name__)

RECALL_PROMPT = """你是一个温暖的记忆助手，帮助用户回忆他们过去记录的生活片段。

以下是与用户问题最相关的几条记忆：

{context}

用户的问题：{question}

请根据以上记忆内容，用自然、亲切的语气回答用户。
- 如果记忆中有相关信息，结合具体内容回答，并提及时间/情绪等细节
- 如果记忆中没有相关信息，坦诚说"我没有找到相关的回忆"
- 不要编造记忆中没有的内容"""


def _build_context(memories: list[dict]) -> str:
    """把检索到的记忆拼成 LLM 能理解的上下文"""
    db = SessionLocal()
    parts = []
    try:
        for i, mem in enumerate(memories, 1):
            db_mem = db.query(Memory).filter(Memory.id == mem["memory_id"]).first()
            if db_mem:
                parts.append(
                    f"记忆{i}（{db_mem.created_at.strftime('%Y-%m-%d %H:%M')}，"
                    f"情绪：{db_mem.sentiment}）：\n"
                    f"摘要：{db_mem.summary}\n"
                    f"原文片段：{db_mem.transcript[:300]}\n"
                )
    finally:
        db.close()
    return "\n".join(parts) if parts else "（暂无相关记忆）"


def recall(question: str) -> dict:
    """
    回忆入口：用户提问→检索→生成回答。

    Args:
        question: 用户的自然语言问题，如"上周我聊了什么开心的事"

    Returns:
        {
            "answer": "LLM 生成的回答",
            "sources": [{"memory_id": int, "summary": str, "distance": float}]
        }
    """
    # Step 1: 向量检索
    results = vector_store.search(question, n_results=3)
    logger.info("检索到 %d 条相关记忆", len(results))

    # Step 2: 没有记忆时的兜底
    if not results:
        return {
            "answer": "你还没有记录过任何记忆哦。先录一段语音，我帮你保存下来吧！",
            "sources": [],
        }

    # Step 3: 拼接上下文
    context = _build_context(results)

    # Step 4: 调用 LLM 生成回答
    prompt = RECALL_PROMPT.format(context=context, question=question)

    try:
        client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("LLM 回答生成失败: %s", str(e))
        # 降级：直接返回检索结果摘要
        answer = "我找到了这些相关的记忆：\n" + "\n".join(
            f"- {r['summary']}" for r in results if r.get("summary")
        )

    return {
        "answer": answer,
        "sources": results,
    }
