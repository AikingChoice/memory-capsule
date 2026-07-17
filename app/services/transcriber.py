# -*- coding: utf-8 -*-
"""
语音转写服务 — 使用 faster-whisper 本地转写，不依赖 OpenAI API。

踩坑记录：
1. faster-whisper 首次运行会下载模型（base约150MB），需要网络
2. 中文音频用 base 模型准确率约 70-80%，用 small 模型能到 85%+，但推理慢一倍
3. 长音频（>5分钟）必须分段处理，否则内存暴涨
4. GPU 可选：有 CUDA 时自动用 GPU，没有时用 CPU（慢3-5倍但能跑）
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# 延迟导入，首次调用时才加载模型（启动快，内存按需分配）
_model = None


def _get_model():
    """懒加载 whisper 模型，避免启动时就占1GB内存"""
    global _model
    if _model is None:
        from app.config import settings
        try:
            from faster_whisper import WhisperModel
            logger.info("加载 Whisper 模型: %s (首次可能需要下载)", settings.whisper_model_size)
            _model = WhisperModel(
                settings.whisper_model_size,
                device="cpu",  # 兼容无GPU环境
                compute_type="int8",  # CPU下用int8量化，省内存
            )
            logger.info("Whisper 模型加载完成")
        except ImportError:
            raise RuntimeError(
                "faster-whisper 未安装。请运行: pip install faster-whisper\n"
                "如果安装失败，可以用 pip install openai-whisper 作为替代"
            )
    return _model


def transcribe(audio_path: str) -> dict:
    """
    转写音频文件为文本。

    Args:
        audio_path: 音频文件路径（支持 mp3/wav/m4a/webm 等常见格式）

    Returns:
        {
            "text": "转写文本",
            "language": "zh",
            "duration": 123.4,
            "segments": [{"start": 0.0, "end": 2.5, "text": "..."}]
        }

    Raises:
        FileNotFoundError: 文件不存在
        RuntimeError: 转写失败
    """
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    file_size_mb = path.stat().st_size / (1024 * 1024)
    logger.info("开始转写: %s (%.1fMB)", path.name, file_size_mb)

    model = _get_model()

    try:
        segments_raw, info = model.transcribe(
            audio_path,
            language="zh",  # 指定中文，避免语言检测误判
            beam_size=5,  # beam search 宽度，越大越准但越慢
            vad_filter=True,  # 启用语音活动检测，跳过静音段
            vad_parameters=dict(
                min_silence_duration_ms=500,  # 静音超过500ms才分段
            ),
        )

        segments = []
        full_text_parts = []
        for seg in segments_raw:
            segments.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
            })
            full_text_parts.append(seg.text.strip())

        full_text = " ".join(full_text_parts)
        duration = info.duration if info.duration else 0

        logger.info("转写完成: %d段, %.1f秒, 语言=%s", len(segments), duration, info.language)

        return {
            "text": full_text,
            "language": info.language,
            "duration": duration,
            "segments": segments,
        }

    except Exception as e:
        logger.error("转写失败: %s", str(e))
        raise RuntimeError(f"音频转写失败: {str(e)}")
