# agent-team-backend

Agent Platform 后端（FastAPI + Microsoft Agent Framework）。

## Vercel 部署

- 依赖已精简：使用 `agent-framework-core` + anthropic/openai。
- `requirements.txt` 由 `uv export --no-dev --no-hashes --no-emit-project` 生成。
- 在 Vercel 配置 `DATABASE_URL`、模型密钥、`AUTH_*` 等（见 `.env.example`）。

## Vercel 环境变量

```bash
npm i -g vercel@latest
export VERCEL_TOKEN='vercel_...'
vercel link
python scripts/sync_vercel_env.py --dry-run
python scripts/sync_vercel_env.py
```

生产环境：`AUTH_COOKIE_SECURE=true`，`CORS_ORIGINS=https://你的前端.vercel.app`

## 本地开发

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
