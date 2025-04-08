import os
from fastapi.security import OAuth2PasswordBearer


# --- 配置 ---
# 用于JWT签名的密钥，请务必替换成你自己的强密钥，并保密！
SECRET_KEY = os.getenv("SECRET_KEY", "YOUR_SECRET_KEY_SHOULD_BE_COMPLEX_AND_SECRET")  # 优先从环境变量读取
ALGORITHM = "HS256"  # 加密算法
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 用户 Access Token 有效期（分钟）- 缩短以便测试
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 用户 Refresh Token 有效期（7天）

# --- GitHub OAuth 配置 ---
# !! 重要：请将你的 GitHub OAuth App 的 Client ID 和 Client Secret 设置为环境变量
# !! 或者直接替换下面的占位符。切勿将 Client Secret 硬编码提交到代码库！
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI",
                                "http://localhost:5550/oauth/v1/code/to/access/auth/github/callback")  # GitHub 应用中配置的回调 URL
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API_URL = "https://api.github.com/user"
GITHUB_SCOPES = "read:user user:email"  # 请求的用户权限范围

# --- OAuth2 配置 (用于提取内部 JWT Token) ---
# 使用 OAuth2PasswordBearer 从 Authorization: Bearer <token> 头提取 token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login/github")  # tokenUrl 指向登录入口，虽然这里不会直接调用

# --- 服务客户端凭证 (模拟) ---
# !! 重要：在真实应用中，这些应该来自安全配置或数据库
SERVICE_CLIENT_ID = os.getenv("SERVICE_CLIENT_ID", "my-trusted-service")
SERVICE_CLIENT_SECRET = os.getenv("SERVICE_CLIENT_SECRET", "super-secret-service-key")
SERVICE_ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 服务 Token 有效期（分钟）


# --- QQ OAuth 配置 ---
# !! 重要：请将你的 QQ 互联应用的 APP ID 和 APP Key 设置为环境变量
# !! 或直接替换占位符。切勿将 APP Key 硬编码提交！
QQ_APP_ID = os.getenv("QQ_APP_ID", "")
QQ_APP_KEY = os.getenv("QQ_APP_KEY", "")
QQ_REDIRECT_URI = os.getenv("QQ_REDIRECT_URI", "http://localhost:5550/oauth/v1/auth/qq/callback")  # 确保与 QQ 互联平台配置一致

QQ_AUTHORIZE_URL = "https://graph.qq.com/oauth2.0/authorize"
QQ_ACCESS_TOKEN_URL = "https://graph.qq.com/oauth2.0/token"
QQ_OPENID_URL = "https://graph.qq.com/oauth2.0/me"
QQ_USER_INFO_URL = "https://graph.qq.com/user/get_user_info"
QQ_SCOPE = "get_user_info"  # 请求的用户权限

# --- 内部 JWT 配置 (QQ 登录用户) ---
# 可以复用全局 SECRET_KEY，或定义独立的
QQ_JWT_SECRET_KEY = os.getenv("QQ_JWT_SECRET_KEY", os.getenv("SECRET_KEY", "a_different_secret_for_qq_jwt"))
QQ_JWT_ALGORITHM = os.getenv("QQ_JWT_ALGORITHM", os.getenv("ALGORITHM", "HS256"))
QQ_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("QQ_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
QQ_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("QQ_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# --- Session 配置 ---
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "global_session_secret_key")
