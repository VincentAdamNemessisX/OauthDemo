from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from config.mock_config import ALGORITHM, SECRET_KEY, SERVICE_CLIENT_ID
from model.mock_model import TokenData, User, ServiceTokenData, fake_users_db
from service.mock_user_service import get_user_by_github_id

# --- 用户认证依赖 ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login/github")


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
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
        token_data = TokenData(github_id=github_id)
    except (JWTError, ValueError):
        # JWT 解码失败或 github_id 格式错误
        raise credentials_exception

    user = get_user_by_github_id(db=fake_users_db, github_id=token_data.github_id)
    if user is None:
        # 虽然 token 有效，但对应的用户可能已被删除
        raise credentials_exception
    return user


async def get_current_active_user(
        current_user: Annotated[User, Depends(get_current_user)]
) -> User:
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
