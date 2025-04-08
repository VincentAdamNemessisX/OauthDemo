import json
import re  # 用于解析 QQ 返回的 callback 内容
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Tuple

import httpx
from jose import jwt

# 导入配置
from config.providers import (
    QQ_APP_ID, QQ_APP_KEY, QQ_REDIRECT_URI,
    QQ_ACCESS_TOKEN_URL, QQ_OPENID_URL, QQ_USER_INFO_URL,
    QQ_JWT_SECRET_KEY, QQ_JWT_ALGORITHM,
    QQ_ACCESS_TOKEN_EXPIRE_MINUTES, QQ_REFRESH_TOKEN_EXPIRE_DAYS
)
# 导入模型
from model.qq_models import QQUserInfo, QQUser

# --- 模拟用户存储 (实际应用应使用数据库) ---
qq_user_db: Dict[str, QQUser] = {}


async def exchange_code_for_qq_token(code: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """使用 code 向 QQ 请求 access_token 和 refresh_token"""
    params = {
        "grant_type": "authorization_code",
        "client_id": QQ_APP_ID,
        "client_secret": QQ_APP_KEY,
        "code": code,
        "redirect_uri": QQ_REDIRECT_URI,
        "fmt": "json"  # 尝试请求 JSON 格式，但可能仍返回 x-www-form-urlencoded
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(QQ_ACCESS_TOKEN_URL, params=params)
            response.raise_for_status()
            # QQ 可能返回 x-www-form-urlencoded 格式: access_token=FE...&expires_in=7776000&refresh_token=88...
            content_type = response.headers.get("content-type", "").lower()
            if "application/json" in content_type:
                data = response.json()
                if "error" in data:
                    print(f"QQ 获取 token 出错(JSON): {data}")
                    return None, None, None
                access_token = data.get("access_token")
                refresh_token = data.get("refresh_token")
                expires_in = data.get("expires_in")
            elif "text/plain" in content_type or "text/html" in content_type:  # 兼容 form-urlencoded
                content = response.text
                data = dict(param.split("=") for param in content.split("&") if "=" in param)
                if "access_token" not in data:
                    print(f"QQ 获取 token 出错(Text): {content}")
                    return None, None, None
                access_token = data.get("access_token")
                refresh_token = data.get("refresh_token")
                expires_in = data.get("expires_in")
            else:
                print(f"QQ 获取 token 返回未知 Content-Type: {content_type}, 内容: {response.text}")
                return None, None, None

            expires_in = int(expires_in) if expires_in else None
            return access_token, refresh_token, expires_in
        except Exception as e:
            print(f"请求 QQ access token 异常: {e}")
            return None, None, None


async def get_qq_openid(access_token: str) -> Optional[str]:
    """使用 access_token 获取用户的 OpenID"""
    params = {"access_token": access_token, "fmt": "json"}  # 尝试 json
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(QQ_OPENID_URL, params=params)
            response.raise_for_status()
            # QQ 返回: callback( {"client_id":"YOUR_APPID","openid":"YOUR_OPENID"} );
            content = response.text
            match = re.search(r'callback\(\s*({.*?})\s*\);?', content)
            if match:
                data = json.loads(match.group(1))
                openid = data.get("openid")
                if not openid:
                    print(f"QQ 获取 openid 返回数据错误: {data}")
                    return None
                return openid
            else:
                # 尝试直接解析 JSON (如果某天 QQ 改了接口)
                try:
                    data = response.json()
                    if data.get("openid"):
                        return data.get("openid")
                except json.JSONDecodeError:
                    pass
                print(f"无法从 QQ 获取 openid: {content}")
                return None
        except Exception as e:
            print(f"请求 QQ openid 异常: {e}")
            return None


async def get_qq_user_info(access_token: str, openid: str) -> Optional[QQUserInfo]:
    """使用 access_token 和 openid 获取用户详细信息"""
    params = {
        "access_token": access_token,
        "oauth_consumer_key": QQ_APP_ID,  # 注意是 oauth_consumer_key
        "openid": openid
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(QQ_USER_INFO_URL, params=params)
            response.raise_for_status()
            data = response.json()
            user_info = QQUserInfo(**data)
            if user_info.ret != 0:
                print(f"QQ 获取用户信息失败: ret={user_info.ret}, msg={user_info.msg}")
                return None
            return user_info
        except Exception as e:
            print(f"请求 QQ user info 异常: {e}")
            return None


def create_internal_qq_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建内部 QQ 用户 Access Token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=QQ_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, QQ_JWT_SECRET_KEY, algorithm=QQ_JWT_ALGORITHM)
    return encoded_jwt


def create_internal_qq_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建内部 QQ 用户 Refresh Token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=QQ_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, QQ_JWT_SECRET_KEY, algorithm=QQ_JWT_ALGORITHM)
    return encoded_jwt


def get_or_create_qq_user(openid: str, user_info: QQUserInfo) -> QQUser:
    """根据 OpenID 查找或创建本地用户 (简化版)"""
    if openid in qq_user_db:
        # 更新用户信息 (可选)
        user = qq_user_db[openid]
        user.nickname = user_info.nickname
        user.avatar_url = user_info.figureurl_qq_2 or user_info.figureurl_qq_1
    else:
        # 创建新用户
        user = QQUser(
            openid=openid,
            nickname=user_info.nickname,
            avatar_url=user_info.figureurl_qq_2 or user_info.figureurl_qq_1
        )
        qq_user_db[openid] = user
    return user


def get_qq_user_by_openid(openid: str) -> Optional[QQUser]:
    """根据 OpenID 获取本地用户"""
    return qq_user_db.get(openid)
