# -*- coding: utf-8 -*-
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Memory(Base):
    """一条语音记忆记录"""
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 原始音频文件路径
    audio_path = Column(String(500), nullable=False)
    # Whisper 转写文本
    transcript = Column(Text, nullable=False)
    # AI 生成的摘要
    summary = Column(Text, default="")
    # AI 提取的关键词，逗号分隔
    keywords = Column(String(500), default="")
    # 情绪标签：positive / neutral / negative
    sentiment = Column(String(20), default="neutral")
    # 情绪分析理由
    sentiment_reason = Column(Text, default="")
    # 音频时长（秒）
    duration_seconds = Column(Float, default=0)
    # 处理状态：pending / processing / done / failed
    status = Column(String(20), default="pending")
    # 错误信息
    error_message = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db():
    """创建所有表"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI 依赖注入用的数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
