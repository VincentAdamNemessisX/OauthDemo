from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from core.router import router
from config.mock_config import SESSION_SECRET_KEY

# --- FastAPI 应用实例 ---
app = FastAPI()
app.include_router(router, prefix="/oauth")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)
