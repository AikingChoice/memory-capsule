# 记忆胶囊

一个语音记忆助手。录音、转写、分析、检索——帮你留住那些容易忘掉的想法。

## 它能干什么

录一段语音或者上传音频文件，系统会自动：
- 用 faster-whisper 在本地把语音转成文字（不走外部 API，隐私安全）
- 调 DeepSeek 对转写内容做摘要、提取关键词、判断情绪
- 把分析结果存进 ChromaDB 向量数据库
- 之后你可以用自然语言提问，比如"上周我聊了什么开心的事"，系统会检索相关记忆并给出回答

整个流程：录音 → 转写 → AI 分析 → 向量存储 → 语义检索

## 技术选型

| 模块 | 用的什么 | 为什么这么选 |
|------|---------|-------------|
| 语音转写 | faster-whisper | 本地跑，不花钱，不依赖 OpenAI，中文支持还行，自带 VAD 过滤静音段 |
| AI 分析 | DeepSeek（主）/ MiMo（备） | 一次调用搞定摘要+关键词+情绪，省 token；DeepSeek 挂了自动切 MiMo |
| 向量存储 | ChromaDB | 轻量，持久化，cosine 相似度，不需要额外起服务 |
| 后端 | FastAPI + SQLAlchemy | 自带 Swagger 文档，依赖注入写起来舒服 |
| 数据库 | SQLite | 零配置，单文件，这个项目规模够用 |
| 前端 | 原生 HTML/CSS/JS | 不想引入前端框架，单文件能搞定就不多加东西 |
| 部署 | Docker | 打包 ffmpeg 依赖，避免环境问题 |

## 快速开始

环境要求：Python 3.10+，ffmpeg

```bash
git clone https://github.com/AikingChoice/memory-capsule.git
cd memory-capsule
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # Linux/Mac
pip install -r requirements.txt
cp .env.example .env           # 填入你的 DeepSeek API Key
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

打开 `http://localhost:8000` 就能用了。

Docker 部署：
```bash
docker-compose up -d
```

## API 接口

启动后 `http://localhost:8000/docs` 有完整的 Swagger 文档，核心接口：

- `POST /api/upload` — 上传音频，后台自动转写+分析
- `GET /api/memories` — 记忆列表，支持分页和情绪筛选
- `GET /api/memories/{id}` — 单条记忆详情
- `DELETE /api/memories/{id}` — 删除记忆
- `GET /api/memories/stats/overview` — 统计概览
- `POST /api/chat` — 对话式检索，问问题，返回基于你记忆的回答
- `GET /health` — 健康检查

## 项目结构

```
app/
├── main.py              # 入口，路由注册
├── config.py            # 配置（pydantic-settings，读 .env）
├── models.py            # SQLAlchemy 模型
├── routes/
│   ├── upload.py        # 上传 + 后台处理
│   ├── memories.py      # CRUD + 统计
│   └── chat.py          # 对话检索
├── services/
│   ├── transcriber.py   # Whisper 转写
│   ├── analyzer.py      # DeepSeek/MiMo 分析
│   ├── vector_store.py  # ChromaDB 存储
│   └── recall.py        # 检索 + LLM 回答
├── templates/
│   └── index.html       # 前端页面
└── static/
tests/
└── test_app.py          # 9 个测试，mock 外部依赖
```

## 开发中踩过的坑

**为什么用 faster-whisper 不用 OpenAI Whisper API？**
一开始用的 OpenAI API，要花钱不说，音频还得传上去。换成 faster-whisper 之后本地跑，零成本，Docker 里打包也方便。唯一要注意的是首次运行要下载模型文件（base 模型大概 150MB）。

**为什么要一次 LLM 调用完成三个任务？**
最初是摘要、关键词、情绪分三次调用，后来发现可以用 JSON mode 一次搞定，token 消耗少了大半，响应也快了不少。prompt 里把三个任务的要求写清楚，模型返回结构化 JSON 就行。

**向量检索精度怎么提上来的？**
最开始拿纯转写文本入库，检索效果一般。后来改成"摘要+关键词+前200字转写"拼在一起入库，语义集中了很多，检索准确率明显好了一些。这个是试出来的，没什么理论依据。

**后台线程 vs 消息队列**
考虑过用 Celery，但这个项目单条音频处理也就几秒的事，用 Thread(daemon=True) 完全够。引入 Redis/Celery 反而增加部署复杂度，不划算。

**模型自动降级**
analyzer.py 里先调 DeepSeek，抛异常就切 MiMo。两个都挂了才报错。实际使用中 DeepSeek 挺稳定的，MiMo 基本没用上，但有这个兜底心里踏实。

## 测试

```bash
pytest tests/ -v
```

测试里 mock 了 Whisper、DeepSeek API 和 ChromaDB，不需要真实 API Key 就能跑。

## License

MIT
