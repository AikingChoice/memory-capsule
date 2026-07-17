# -*- coding: utf-8 -*-
import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 主模型（任意 OpenAI 兼容接口）
    primary_api_key: str = ""
    primary_base_url: str = "https://api.deepseek.com"
    primary_model: str = "deepseek-chat"

    # 备用模型（主模型挂了自动切换）
    backup_api_key: str = ""
    backup_base_url: str = ""
    backup_model: str = ""

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
