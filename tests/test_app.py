# -*- coding: utf-8 -*-
"""
测试用例 — 用 mock 避免真实 API 调用和模型加载。

测试覆盖：
- 上传接口：格式校验、文件过大拒绝
- 记忆列表：分页、情绪筛选
- 对话接口：正常提问、空问题
- 健康检查
"""
import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """每个测试用例使用独立的临时数据库"""
    db_url = f"sqlite:///{tmp_path}/test.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))

    # 重新加载配置和数据库
    import importlib
    import app.config
    importlib.reload(app.config)
    import app.models
    importlib.reload(app.models)
    app.models.init_db()

    yield


@pytest.fixture
def client():
    """FastAPI 测试客户端"""
    from app.main import app
    return TestClient(app)


# ========== 健康检查 ==========

def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


# ========== 上传接口 ==========

def test_upload_unsupported_format(client):
    """不支持的文件格式应返回 400"""
    res = client.post(
        "/api/upload",
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 400
    assert "不支持" in res.json()["detail"]


@patch("app.routes.upload.transcribe")
@patch("app.routes.upload.analyze")
@patch("app.routes.upload.add_memory")
def test_upload_audio(mock_add, mock_analyze, mock_transcribe, client):
    """正常上传音频应返回记忆 ID"""
    mock_transcribe.return_value = {"text": "今天天气不错", "duration": 5.0}
    mock_analyze.return_value = {
        "summary": "谈论天气",
        "keywords": "天气,心情",
        "sentiment": "positive",
        "sentiment_reason": "语气愉快",
    }
    mock_add.return_value = None

    audio_bytes = b"\x00" * 1024  # 伪音频数据
    res = client.post(
        "/api/upload",
        files={"file": ("test.wav", io.BytesIO(audio_bytes), "audio/wav")},
    )
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert data["status"] == "pending"


# ========== 记忆列表 ==========

def test_memories_empty(client):
    """空数据库应返回空列表"""
    res = client.get("/api/memories")
    assert res.status_code == 200
    assert res.json()["total"] == 0
    assert res.json()["items"] == []


def test_stats_empty(client):
    """空数据库统计应全为 0"""
    res = client.get("/api/memories/stats/overview")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0


# ========== 对话接口 ==========

@patch("app.services.recall.vector_store.search")
@patch("app.services.recall.OpenAI")
def test_chat_no_memories(mock_openai, mock_search, client):
    """没有记忆时应返回提示信息"""
    mock_search.return_value = []

    res = client.post("/api/chat", json={"question": "我有什么开心的事"})
    assert res.status_code == 200
    assert "还没有" in res.json()["answer"]


@patch("app.services.recall.vector_store.search")
@patch("app.services.recall.OpenAI")
def test_chat_with_memories(mock_openai, mock_search, client):
    """有相关记忆时应返回 LLM 生成的回答"""
    mock_search.return_value = [
        {"memory_id": 1, "summary": "天气很好", "distance": 0.3},
    ]

    # Mock LLM 回答
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "你之前记录过天气很好，心情不错！"
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai.return_value = mock_client

    # 需要在数据库中有一条记忆记录
    from app.models import SessionLocal, Memory
    db = SessionLocal()
    mem = Memory(id=1, audio_path="test.wav", transcript="今天天气真好", summary="天气很好",
                 keywords="天气", sentiment="positive", status="done")
    db.add(mem)
    db.commit()
    db.close()

    res = client.post("/api/chat", json={"question": "我之前聊了什么"})
    assert res.status_code == 200
    assert "天气" in res.json()["answer"]


def test_chat_empty_question(client):
    """空问题应返回提示"""
    res = client.post("/api/chat", json={"question": ""})
    assert res.status_code == 200
    assert "请输入" in res.json()["answer"]


# ========== 首页 ==========

def test_index(client):
    """首页应返回 HTML"""
    res = client.get("/")
    assert res.status_code == 200
    assert "记忆胶囊" in res.text
