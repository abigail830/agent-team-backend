# agent-team-backend

Agent Platform 后端：FastAPI + Microsoft Agent Framework。

## 本地开发

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env   # 填写 DATABASE_URL、模型密钥等
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## 登录与用户

平台使用邮箱 + 密码登录，会话为 HttpOnly Cookie + 服务端 session。

```bash
python scripts/set_user_password.py --email you@example.com --name "Your Name"
```

| 变量 | 说明 |
|------|------|
| `AUTH_DISABLED` | `true` 时免登录（仅开发） |
| `AUTH_COOKIE_NAME` | Session cookie 名，默认 `ap_session` |
| `AUTH_SESSION_TTL_HOURS` | 会话有效期（小时），默认 168 |
| `AUTH_COOKIE_SECURE` | 生产 HTTPS 下设 `true` |

完整环境变量见 `.env.example`。

## 健康检查

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/docs
```
