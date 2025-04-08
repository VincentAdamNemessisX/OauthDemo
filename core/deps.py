from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
# 导入模型
from model.mocker.mock_model import GithubUser, GithubTokenData  # 假设 GitHub 模型在此
from model.mocker.mock_model import ServiceTokenData  # 假设 Service 模型在此

# 导入全局配置和特定提供商的配置
from config.providers import (
    QQ_JWT_SECRET_KEY, QQ_JWT_ALGORITHM,  # QQ JWT 配置
    GITHUB_CLIENT_ID,
    SERVICE_CLIENT_ID,
    ALGORITHM, SECRET_KEY,
)
from model.mocker.mock_model import GithubTokenData, GithubUser, ServiceTokenData, fake_users_db
from model.qq_models import QQUser, QQTokenData  # 导入 QQ 模型
from service.mocker.mock_user_service import get_user_by_github_id
from service.qq_oauth_service import get_qq_user_by_openid  # 导入 QQ 服务

# --- 用户认证依赖 ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login/github")


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> GithubUser:
    """
    依赖函数：解码并验证内部 JWT Token，返回当前用户。
    Token 从 Authorization: Bearer Header 中提取。
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        github_id_str: str = payload.get("sub")  # 从 'sub' 字段获取 github_id (之前存的是 username)
        if github_id_str is None:
            raise credentials_exception
        github_id = int(github_id_str)
        token_data = GithubTokenData(github_id=github_id)
    except (JWTError, ValueError):
        # JWT 解码失败或 github_id 格式错误
        raise credentials_exception

    user = get_user_by_github_id(db=fake_users_db, github_id=token_data.github_id)
    if user is None:
        # 虽然 token 有效，但对应的用户可能已被删除
        raise credentials_exception
    return user


async def get_current_active_user(
        current_user: Annotated[GithubUser, Depends(get_current_user)]
) -> GithubUser:
    """检查当前用户是否是激活状态"""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    return current_user


# --- 服务认证依赖 ---
# 这里的 tokenUrl 仅用于文档显示，实际验证在 get_current_service 中
service_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/service/token")


async def get_current_service(token: Annotated[str, Depends(service_oauth2_scheme)]) -> ServiceTokenData:
    """
    依赖函数：解码并验证服务的 JWT Token。
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证服务凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        client_id: str = payload.get("sub")
        scopes = payload.get("scopes", [])
        if client_id is None:
            raise credentials_exception
        # 可以在这里添加额外的检查，例如 client_id 是否是我们定义的服务 ID
        if client_id != SERVICE_CLIENT_ID:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未授权的服务客户端")

        token_data = ServiceTokenData(client_id=client_id, scopes=scopes)
    except JWTError:
        raise credentials_exception
    return token_data


# --- QQ 用户认证依赖 ---
qq_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/oauth/v1/login/qq")  # 指向 QQ 登录入口


async def get_current_qq_user(token: Annotated[str, Depends(qq_oauth2_scheme)]) -> QQUser:
    """依赖函数：解码并验证内部 QQ 用户 JWT Token，返回本地 QQ 用户信息"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证 QQ 用户凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, QQ_JWT_SECRET_KEY, algorithms=[QQ_JWT_ALGORITHM])
        openid: str = payload.get("sub")
        if openid is None:
            raise credentials_exception
        token_data = QQTokenData(openid=openid)
    except JWTError:
        raise credentials_exception

    # 从本地存储 (模拟数据库) 中查找用户
    user = get_qq_user_by_openid(openid=token_data.openid)
    if user is None:
        # Token 有效，但用户可能已在本地被删除
        raise credentials_exception
    # 可选：在这里添加用户是否被禁用的检查
    # if user.disabled:
    #     raise HTTPException(status_code=400, detail="用户已被禁用")
    return user
