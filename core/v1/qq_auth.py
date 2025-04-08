import secrets
from datetime import timedelta
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import RedirectResponse
# 导入 JWT 处理库
from jose import JWTError, jwt

# 导入配置
from config.providers import (
    QQ_APP_ID, QQ_REDIRECT_URI, QQ_AUTHORIZE_URL, QQ_SCOPE,
    QQ_ACCESS_TOKEN_EXPIRE_MINUTES, QQ_REFRESH_TOKEN_EXPIRE_DAYS,
    QQ_JWT_SECRET_KEY, QQ_JWT_ALGORITHM  # 用于刷新 Token 验证
)
# 导入依赖
from core.deps import get_current_qq_user
# 导入模型
from model.qq_models import QQToken, QQUser, QQTokenData
# 导入服务
from service.qq_oauth_service import (
    exchange_code_for_qq_token, get_qq_openid, get_qq_user_info,
    get_or_create_qq_user, get_qq_user_by_openid,  # 用于刷新时查找用户
    create_internal_qq_access_token, create_internal_qq_refresh_token
)

router = APIRouter(
    prefix="/auth/qq",  # 给 QQ 路由加个前缀，避免和 GitHub/Service 冲突
    tags=["QQ Authentication (v1)"]
)


@router.get("/login")
async def login_via_qq(request: Request):
    """重定向用户到 QQ 授权页面"""
    state = secrets.token_urlsafe(32)
    request.session["qq_oauth_state"] = state  # 使用独立的 session key
    params = {
        "response_type": "code",
        "client_id": QQ_APP_ID,
        "redirect_uri": QQ_REDIRECT_URI,
        "state": state,
        "scope": QQ_SCOPE,
    }
    qq_auth_url = f"{QQ_AUTHORIZE_URL}?{urlencode(params)}"
    return RedirectResponse(qq_auth_url)


@router.get("/callback", response_model=QQToken)
async def auth_qq_callback(request: Request, code: str, state: str):
    """处理 QQ 回调，完成认证流程并返回内部 Token"""
    # 1. 验证 state
    expected_state = request.session.get("qq_oauth_state")
    if not expected_state or state != expected_state:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无效的 state 参数")
    request.session.pop("qq_oauth_state", None)

    # 2. 用 code 换取 QQ access token
    access_token, qq_refresh_token, expires_in = await exchange_code_for_qq_token(code)
    if not access_token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="无法从 QQ 获取 Access Token")

    # 3. 用 access_token 获取 openid
    openid = await get_qq_openid(access_token)
    if not openid:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="无法从 QQ 获取 OpenID")

    # 4. 用 access_token 和 openid 获取用户信息
    user_info = await get_qq_user_info(access_token, openid)
    if not user_info:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="无法从 QQ 获取用户信息")

    # 5. 在本地查找或创建用户
    local_user = get_or_create_qq_user(openid, user_info)

    # 6. 创建内部 Access Token 和 Refresh Token
    internal_access_token_expires = timedelta(minutes=QQ_ACCESS_TOKEN_EXPIRE_MINUTES)
    internal_refresh_token_expires = timedelta(days=QQ_REFRESH_TOKEN_EXPIRE_DAYS)

    internal_access_token = create_internal_qq_access_token(
        data={"sub": local_user.openid}, expires_delta=internal_access_token_expires
    )
    internal_refresh_token = create_internal_qq_refresh_token(
        data={"sub": local_user.openid}, expires_delta=internal_refresh_token_expires
    )

    # 7. 返回内部 Token
    return QQToken(access_token=internal_access_token, refresh_token=internal_refresh_token)


@router.post("/token/refresh", response_model=QQToken)
async def refresh_qq_token(
        refresh_token: Annotated[str, Form()]
):
    """使用内部 Refresh Token 获取新的内部 Access Token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证 QQ Refresh Token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(refresh_token, QQ_JWT_SECRET_KEY, algorithms=[QQ_JWT_ALGORITHM])
        openid: str = payload.get("sub")
        if openid is None:
            raise credentials_exception
        # 可选: 检查 purpose
        token_data = QQTokenData(openid=openid)
    except JWTError:
        raise credentials_exception

    # 检查用户是否存在且未禁用
    user = get_qq_user_by_openid(openid=token_data.openid)
    if user is None:
        raise credentials_exception
    # 可选: if user.disabled: raise ...

    # 创建新的 Access Token
    new_access_token_expires = timedelta(minutes=QQ_ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_internal_qq_access_token(
        data={"sub": user.openid}, expires_delta=new_access_token_expires
    )

    # 返回新的 Access Token，通常不返回 Refresh Token
    return QQToken(access_token=new_access_token)


# 可选：受保护的用户端点
@router.get("/users/me", response_model=QQUser)
async def read_current_qq_user(
        current_user: Annotated[QQUser, Depends(get_current_qq_user)]
):
    """获取当前通过 QQ 登录的用户信息 (来自本地存储)"""
    return current_user
