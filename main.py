import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Union, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

# --- 配置 ---
# 用于JWT签名的密钥，请务必替换成你自己的强密钥，并保密！
SECRET_KEY = os.getenv("SECRET_KEY", "YOUR_SECRET_KEY_SHOULD_BE_COMPLEX_AND_SECRET")  # 优先从环境变量读取
ALGORITHM = "HS256"  # 加密算法
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 内部 JWT Token 有效期（分钟）

# --- GitHub OAuth 配置 ---
# !! 重要：请将你的 GitHub OAuth App 的 Client ID 和 Client Secret 设置为环境变量
# !! 或者直接替换下面的占位符。切勿将 Client Secret 硬编码提交到代码库！
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI",
                                "http://localhost:5550/auth/github/callback")  # GitHub 应用中配置的回调 URL
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API_URL = "https://api.github.com/user"
GITHUB_SCOPES = "read:user user:email"  # 请求的用户权限范围

# --- OAuth2 配置 (用于提取内部 JWT Token) ---
# 使用 OAuth2PasswordBearer 从 Authorization: Bearer <token> 头提取 token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login/github")  # tokenUrl 指向登录入口，虽然这里不会直接调用

# --- 模拟用户数据库 ---
# 存储通过 GitHub 登录的用户信息
# key 可以是 GitHub 用户名或者应用内部的用户 ID
fake_users_db = {}


# --- Pydantic 模型 ---
class User(BaseModel):
    """用户模型，用于数据校验和响应"""
    username: str  # GitHub 用户名
    github_id: int  # GitHub 用户 ID
    name: Optional[str] = None  # GitHub 上的名字
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    disabled: bool = False


# 添加 Token 定义
class Token(BaseModel):
    """Token 响应模型 (返回我们自己生成的 JWT)"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """解码后的内部 JWT Token 数据模型"""
    # 使用 github_id 作为用户标识符会更稳定，因为 username 可能改变
    github_id: Optional[int] = None


# --- 辅助函数 ---
def get_user_by_github_id(db, github_id: int) -> Optional[User]:
    """根据 GitHub ID 从模拟数据库获取用户"""
    # 实际应用中这里应该是数据库查询
    for user in db.values():
        if user.github_id == github_id:
            return user
    return None


def add_or_update_user(db, user_data: dict) -> User:
    """根据从 GitHub 获取的数据添加或更新用户"""
    github_id = user_data.get("id")
    if not github_id:
        raise ValueError("GitHub user data must contain 'id'")

    existing_user = get_user_by_github_id(db, github_id)

    user_info = User(
        username=user_data.get("login"),
        github_id=github_id,
        name=user_data.get("name"),
        email=user_data.get("email"),
        avatar_url=user_data.get("avatar_url"),
        disabled=existing_user.disabled if existing_user else False  # 保留之前的禁用状态
    )

    # 使用 github_id 作为 key 存储用户，更可靠
    db[github_id] = user_info
    return user_info


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


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
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

    user = get_user_by_github_id(fake_users_db, github_id=token_data.github_id)
    if user is None:
        # 虽然 token 有效，但对应的用户可能已被删除
        raise credentials_exception
    return user


async def get_current_active_user(
        current_user: Annotated[User, Depends(get_current_user)]
):
    """检查当前用户是否是激活状态"""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    return current_user


# --- FastAPI 应用实例 ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# --- 临时存储 state 和对应的 redirect_uri ---
# 生产环境应该使用更健壮的存储，如 Redis 或数据库，并设置过期时间
# 或者使用签名的 state 参数
temp_state_store = {}


# --- API 端点 ---
@app.get("/login/github")
async def login_via_github(request: Request, redirect_uri: Optional[str] = None):
    """将用户重定向到 GitHub 进行认证"""
    # 生成一个随机的 state 参数用于防止 CSRF
    state = secrets.token_urlsafe(32)

    # 构造 GitHub 授权 URL
    github_auth_url = (
        f"{GITHUB_AUTHORIZE_URL}?"
        f"client_id={GITHUB_CLIENT_ID}&"
        f"redirect_uri={GITHUB_REDIRECT_URI}&"
        f"scope={GITHUB_SCOPES}&"
        f"state={state}"
    )

    # 存储 state 和原始请求的 redirect_uri (如果提供)
    # 实际应用中需要更安全的处理方式
    request.session["oauth_state"] = state  # 使用 FastAPI SessionMiddleware (需安装 starlette[full])
    # 如果没有 SessionMiddleware，可以考虑其他方式存储 state
    # temp_state_store[state] = redirect_uri or "/" # 简单示例，非生产级

    return RedirectResponse(github_auth_url)


@app.get("/auth/github/callback")
async def auth_github_callback(request: Request, code: str, state: str):
    """处理 GitHub 回调，用 code 换取 token 并获取用户信息"""
    # 验证 state 防止 CSRF
    expected_state = request.session.get("oauth_state")
    if not expected_state or state != expected_state:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无效的 state 参数")
    # 验证后清除 state
    request.session.pop("oauth_state", None)

    # --- 步骤 1: 用 code 换取 GitHub Access Token ---
    token_payload = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": GITHUB_REDIRECT_URI,
    }
    headers = {"Accept": "application/json"}  # 要求 GitHub 返回 JSON 格式

    async with httpx.AsyncClient(proxy="http://localhost:22223") as client:
        try:
            token_response = await client.post(
                GITHUB_ACCESS_TOKEN_URL,
                json=token_payload,
                headers=headers,
            )
            token_response.raise_for_status()  # 如果请求失败则抛出异常
            token_data = token_response.json()
        except httpx.HTTPStatusError as e:
            print(f"获取 GitHub token 时出错: {e.response.text}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="无法从 GitHub 获取 Token")
        except Exception as e:
            print(f"请求 GitHub token 时发生错误: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="请求 GitHub Token 时出错")

    github_token = token_data.get("access_token")
    if not github_token:
        print(f"GitHub token 响应中缺少 access_token: {token_data}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="GitHub 响应无效")

    # --- 步骤 2: 用 GitHub Access Token 获取用户信息 ---
    user_headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    async with httpx.AsyncClient() as client:
        try:
            user_response = await client.get(GITHUB_USER_API_URL, headers=user_headers)
            user_response.raise_for_status()
            user_data = user_response.json()
        except httpx.HTTPStatusError as e:
            print(f"获取 GitHub 用户信息时出错: {e.response.text}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="无法获取 GitHub 用户信息")
        except Exception as e:
            print(f"请求 GitHub 用户信息时发生错误: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="请求 GitHub 用户信息时出错")

    if not user_data or "id" not in user_data:
        print(f"无效的 GitHub 用户数据: {user_data}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="无法解析 GitHub 用户数据")

    # --- 步骤 3: 在本地数据库中查找或创建用户 ---
    user = add_or_update_user(fake_users_db, user_data)

    # --- 步骤 4: 创建内部 JWT Token ---
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # 使用 github_id 作为 JWT 的 subject ('sub')
    internal_jwt_token = create_access_token(
        data={"sub": str(user.github_id)}, expires_delta=access_token_expires
    )

    # --- 步骤 5: 返回内部 JWT Token 给客户端 ---
    # 这里直接在响应体中返回 Token
    # 也可以设置 HttpOnly Cookie
    response_data = Token(access_token=internal_jwt_token, token_type="bearer")

    # 可以选择重定向到前端页面，并将 token 作为参数或 fragment
    # return RedirectResponse(url="/?token=" + internal_jwt_token)
    # 或者直接返回 JSON
    return response_data


@app.get("/users/me/", response_model=User)
async def read_users_me(
        current_user: Annotated[User, Depends(get_current_active_user)]
):
    """受保护的端点，返回当前登录用户信息"""
    return current_user


@app.get("/users/me/items/")
async def read_own_items(
        current_user: Annotated[User, Depends(get_current_active_user)]
):
    """另一个受保护的端点示例，返回当前用户拥有的物品"""
    # 注意：现在 owner 是 github_id
    return [{"item_id": "Foo", "owner_github_id": current_user.github_id}]


@app.get("/")
async def root():
    """根路径，可以显示登录按钮"""
    # 这里可以返回一个简单的 HTML 页面，包含一个指向 /login/github 的链接
    return {"message": "欢迎! 请访问 /login/github 来通过 GitHub 登录。"}


# 原有的 /hello/{name} 端点，保持公共访问
@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
