import secrets
from datetime import timedelta
from typing import Annotated  # 添加 Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form  # 添加 Form
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt  # 导入 JWTError 和 jwt 用于刷新

# 导入配置
from config.mock_config import (
    GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_REDIRECT_URI,
    GITHUB_AUTHORIZE_URL, GITHUB_ACCESS_TOKEN_URL, GITHUB_USER_API_URL,
    GITHUB_SCOPES, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_MINUTES  # 导入有效期
)
from config.mock_config import SECRET_KEY, ALGORITHM  # 导入密钥和算法用于刷新
# 导入依赖
from core.deps import get_current_active_user  # 导入 get_current_user 用于刷新
# 导入模型
from model.mock_model import Token, User, TokenData, fake_users_db  # 确保 Token 已更新
from service.mock_token_service import create_access_token, create_refresh_token  # 导入 create_refresh_token
# 导入服务
from service.mock_user_service import add_or_update_user, get_user_by_github_id  # 导入 get_user_by_github_id

router = APIRouter(
    tags=["User Authentication (v1)"],
    prefix="/code/to/access"
)


@router.get("/")
async def root(request: Request):
    return "Please use `/login/github` to access protected endpoints."


@router.get("/login/github")
async def login_via_github(request: Request):
    # ... (现有 login_via_github 保持不变) ...
    state = secrets.token_urlsafe(32)
    github_auth_url = (
        f"{GITHUB_AUTHORIZE_URL}?"
        f"client_id={GITHUB_CLIENT_ID}&"
        f"redirect_uri={GITHUB_REDIRECT_URI}&"
        f"scope={GITHUB_SCOPES}&"
        f"state={state}"
    )
    request.session["oauth_state"] = state
    return RedirectResponse(github_auth_url)


@router.get("/auth/github/callback", response_model=Token)
async def code_to_access(request: Request, code: str, state: str):
    """处理 GitHub 回调，用 code 换取 token 并获取用户信息，现在返回 Access 和 Refresh Token"""
    # 验证 state 防止 CSRF
    expected_state = request.session.get("oauth_state")
    if not expected_state or state != expected_state:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无效的 state 参数")
    request.session.pop("oauth_state", None)

    # --- 步骤 1: 用 code 换取 GitHub Access Token ---
    # ... (保持不变) ...
    token_payload = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": GITHUB_REDIRECT_URI,
    }
    headers = {"Accept": "application/json"}
    async with httpx.AsyncClient() as client:
        try:
            token_response = await client.post(GITHUB_ACCESS_TOKEN_URL, json=token_payload, headers=headers)
            token_response.raise_for_status()
            token_data = token_response.json()
        except Exception as e:
            # 简化错误处理
            print(f"获取 GitHub token 出错: {e}")
            raise HTTPException(status_code=500, detail="无法从 GitHub 获取 Token")
    github_token = token_data.get("access_token")
    if not github_token:
        raise HTTPException(status_code=500, detail="GitHub 响应无效")

    # --- 步骤 2: 用 GitHub Access Token 获取用户信息 ---
    # ... (保持不变) ...
    user_headers = {"Authorization": f"token {github_token}"}
    async with httpx.AsyncClient() as client:
        try:
            user_response = await client.get(GITHUB_USER_API_URL, headers=user_headers)
            user_response.raise_for_status()
            user_data = user_response.json()
        except Exception as e:
            print(f"获取 GitHub 用户信息出错: {e}")
            raise HTTPException(status_code=500, detail="无法获取 GitHub 用户信息")
    if not user_data or "id" not in user_data:
        raise HTTPException(status_code=500, detail="无法解析 GitHub 用户数据")

    # --- 步骤 3: 在本地数据库中查找或创建用户 ---
    user = add_or_update_user(fake_users_db, user_data)

    # --- 步骤 4: 创建内部 JWT Access Token 和 Refresh Token ---
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)

    access_token = create_access_token(
        data={"sub": str(user.github_id)}, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.github_id)}, expires_delta=refresh_token_expires
    )

    # --- 步骤 5: 返回内部 JWT Token 给客户端 ---
    return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer")


@router.post("/token/refresh", response_model=Token)
async def refresh_access_token(
        refresh_token: Annotated[str, Form()]
):
    """使用 Refresh Token 获取新的 Access Token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证 Refresh Token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # 解码 Refresh Token
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        github_id_str: str = payload.get("sub")
        if github_id_str is None:
            raise credentials_exception
        # 可选：检查 payload 中是否有标识表明这确实是 Refresh Token
        # if payload.get("token_purpose") != "refresh":
        #     raise credentials_exception

        github_id = int(github_id_str)
        token_data = TokenData(github_id=github_id)
    except (JWTError, ValueError):
        raise credentials_exception

    # 检查用户是否存在 (用户可能已被删除)
    user = get_user_by_github_id(db=fake_users_db, github_id=token_data.github_id)
    if user is None or user.disabled:
        raise credentials_exception  # 或者可以返回 403 Forbidden

    # 创建新的 Access Token (Refresh Token 保持不变或可选地也刷新)
    new_access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(
        data={"sub": str(user.github_id)}, expires_delta=new_access_token_expires
    )

    # 返回新的 Access Token (不返回 Refresh Token，除非实现了刷新令牌轮换)
    return Token(access_token=new_access_token, token_type="bearer")


# --- 受保护的用户端点 --- (保持不变)
@router.get("/users/me/", response_model=User)
async def read_users_me(
        current_user: Annotated[User, Depends(get_current_active_user)]
):
    return current_user


@router.get("/users/me/items/")
async def read_own_items(
        current_user: Annotated[User, Depends(get_current_active_user)]
):
    return [{"item_id": "Foo", "owner_github_id": current_user.github_id}]
