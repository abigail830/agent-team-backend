# agent-team-backend

Agent Platform 后端（FastAPI + Microsoft Agent Framework）。

## Vercel 部署

- 依赖已精简：使用 `agent-framework-core` + anthropic/openai，**不要**安装 meta 包 `agent-framework`（会拉取 ~700MB 可选依赖，超过 Vercel 500MB 限制）。
- `requirements.txt` 由 `uv export --no-dev --no-hashes --no-emit-project` 生成。
- 在 Vercel 项目 Environment Variables 中配置 `DATABASE_URL`、模型密钥、`AUTH_*` 等（见 `.env.example`）。

## 本地开发

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## 注意

FastAPI 含 SSE 长连接与 MCP 子进程，Vercel Serverless 可能仍有超时/冷启动限制。若聊天流式不稳定，建议改用 Railway / Render / Fly.io。
