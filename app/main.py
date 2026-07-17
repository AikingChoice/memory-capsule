# -*- coding: utf-8 -*-
"""
记忆胶囊 — FastAPI 应用入口。

一个 AI 语音记忆助手：
录音 → Whisper 转写 → DeepSeek 分析(摘要/关键词/情绪) → ChromaDB 向量存储 → 自然语言检索回忆
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.models import init_db
from app.routes.upload import router as upload_router
from app.routes.memories import router as memories_router
from app.routes.chat import router as chat_router

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库"""
    logger.info("正在初始化数据库...")
    init_db()
    logger.info("数据库初始化完成")
    yield
    logger.info("应用关闭")


app = FastAPI(
    title="记忆胶囊",
    description="AI 语音记忆助手 — 录音、转写、分析、检索你的回忆",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS：允许前端跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(upload_router)
app.include_router(memories_router)
app.include_router(chat_router)

# 静态文件
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
async def index():
    """首页：返回前端页面"""
    return FileResponse("app/templates/index.html")


@app.get("/health")
def health():
    """健康检查"""
    return {"status": "ok", "service": "memory-capsule"}
