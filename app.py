from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from config.providers import SESSION_SECRET_KEY
from core.router import router

# --- FastAPI 应用实例 ---
app = FastAPI(title="OAuth Demo App")

# --- 中间件 --- (确保顺序)
# 跨域中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应配置具体的来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session 中间件 (用于存储 OAuth state)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,  # 确保这里使用了正确的密钥
    # https_only=True, # 生产环境建议启用
    # max_age=... # 可选：设置 session cookie 过期时间
)

# --- 包含主路由 ---
app.include_router(router)

# --- 可选：根路径提供登录选项 ---
from fastapi.responses import HTMLResponse


@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <html>
        <head><title>OAuth Demo</title></head>
        <body>
            <h1>Login Options</h1>
            <ul>
                <li><a href="/oauth/v1/auth/qq/login">Login with QQ</a></li>
                <li><a href="/oauth/v1/code/to/access/login/github">Login with GitHub</a></li>
                <li>Service Login (Use API)</li>
            </ul>
        </body>
    </html>
    """
