from datetime import timedelta, timezone, datetime
from typing import Union

from jose import jwt

from config.mock_config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY, SERVICE_ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_MINUTES


def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    """创建内部 Access Token (JWT)"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    # 将 github_id 放入 'sub' 字段
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Union[timedelta, None] = None) -> str:
    """创建用户 Refresh Token (JWT)"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_service_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """为服务客户端创建 Access Token (JWT)"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=SERVICE_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    # 使用 client_id 作为 'sub'
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
