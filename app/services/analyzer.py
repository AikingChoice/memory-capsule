# -*- coding: utf-8 -*-
"""
AI 分析服务 — 用 DeepSeek/MiMo 对转写文本做摘要、关键词提取、情绪分析。

设计思路：
- 一次 API 调用完成三个任务（摘要+关键词+情绪），省 token
- 用 JSON mode 让模型输出结构化数据，避免正则解析出错
- 备用模型自动切换：DeepSeek 挂了切 MiMo
"""
import json
import logging
from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)


def _get_client(use_backup: bool = False) -> OpenAI:
    """获取 LLM 客户端，use_backup=True 时切到 MiMo"""
    if use_backup and settings.mimo_api_key:
        return OpenAI(
            api_key=settings.mimo_api_key,
            base_url=settings.mimo_base_url,
        )
    return OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )


ANALYSIS_PROMPT = """你是一个记忆分析助手。请分析以下语音转写文本，返回 JSON 格式的结果。

要求：
1. summary：用1-2句话概括这段话的核心内容（不超过100字）
2. keywords：提取3-5个关键词，用逗号分隔
3. sentiment：情绪标签，只能是 positive / neutral / negative 之一
4. sentiment_reason：一句话解释为什么是这个情绪

文本内容：
{text}

请严格按以下 JSON 格式返回，不要加任何其他文字：
{{"summary": "...", "keywords": "...,...", "sentiment": "...", "sentiment_reason": "..."}}"""


def analyze(text: str) -> dict:
    """
    对转写文本做 AI 分析。

    Args:
        text: Whisper 转写后的文本

    Returns:
        {
            "summary": "摘要",
            "keywords": "关键词1,关键词2",
            "sentiment": "positive|neutral|negative",
            "sentiment_reason": "理由"
        }

    Raises:
        RuntimeError: 两个模型都调用失败
    """
    if not text.strip():
        return {
            "summary": "（空音频，无内容）",
            "keywords": "",
            "sentiment": "neutral",
            "sentiment_reason": "无语音内容",
        }

    # 文本太长时截断，避免超 token 限制
    max_chars = 2000
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
        logger.warning("文本过长，截断至 %d 字符", max_chars)

    prompt = ANALYSIS_PROMPT.format(text=text)

    # 先试 DeepSeek，失败切 MiMo
    for use_backup in [False, True]:
        model_name = "MiMo" if use_backup else "DeepSeek"
        try:
            client = _get_client(use_backup=use_backup)
            logger.info("调用 %s 分析文本 (%d 字符)", model_name, len(text))

            response = client.chat.completions.create(
                model="deepseek-chat" if not use_backup else "MiMo-v2.5-Pro",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # 低温度，输出更稳定
                max_tokens=300,
            )

            raw = response.choices[0].message.content.strip()
            # 处理模型可能返回的 markdown 代码块
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            result = json.loads(raw)

            # 校验必要字段
            for key in ["summary", "keywords", "sentiment", "sentiment_reason"]:
                if key not in result:
                    raise ValueError(f"缺少字段: {key}")

            # 校验 sentiment 合法性
            if result["sentiment"] not in ("positive", "neutral", "negative"):
                result["sentiment"] = "neutral"

            logger.info("分析完成: 情绪=%s, 关键词=%s", result["sentiment"], result["keywords"])
            return result

        except Exception as e:
            logger.warning("%s 分析失败: %s", model_name, str(e))
            if use_backup:  # 两个都失败了
                raise RuntimeError(f"AI 分析失败（DeepSeek 和 MiMo 均不可用）: {str(e)}")

    # 不会走到这里，但保险起见
    raise RuntimeError("AI 分析失败")
