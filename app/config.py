# -*- coding: utf-8 -*-
import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    # MiMo (备用)
    mimo_api_key: str = ""
    mimo_base_url: str = "https://api.xiaomi.com/v1"

    # 应用
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "sqlite:///./data/memory.db"
    chroma_path: str = "./data/chroma"
    whisper_model_size: str = "base"

    # 上传限制
    max_audio_size_mb: int = 50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# 确保数据目录存在
Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
Path("./data").mkdir(parents=True, exist_ok=True)
