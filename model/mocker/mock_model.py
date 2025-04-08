from typing import Optional

from pydantic import BaseModel

# --- 模拟用户数据库 ---
# 存储通过 GitHub 登录的用户信息
# key 可以是 GitHub 用户名或者应用内部的用户 ID
fake_users_db = {}


# --- Pydantic 模型 ---
class GithubUser(BaseModel):
    """用户模型，用于数据校验和响应"""
    username: str  # GitHub 用户名
    github_id: int  # GitHub 用户 ID
    name: Optional[str] = None  # GitHub 上的名字
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    disabled: bool = False


# --- 用户认证相关模型 ---
class Token(BaseModel):
    """包含 Access 和 Refresh Token 的响应模型"""
    access_token: str
    refresh_token: str | None = None  # 添加 refresh_token 字段
    token_type: str


class GithubTokenData(BaseModel):
    """解码后的用户 JWT Token 数据模型 (Access Token 或 Refresh Token)"""
    # 使用 github_id 作为用户标识符
    github_id: int | None = None
    # 可以添加一个字段来区分是 Access 还是 Refresh Token (可选)
    # token_purpose: str | None = None # e.g., "access", "refresh"


# --- 服务认证相关模型 ---
class ServiceToken(BaseModel):
    """服务 Token 响应模型"""
    access_token: str
    token_type: str


class ServiceTokenData(BaseModel):
    """解码后的服务 JWT Token 数据模型"""
    client_id: str | None = None
    scopes: list[str] = []
