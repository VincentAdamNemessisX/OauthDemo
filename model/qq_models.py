from pydantic import BaseModel


# --- QQ API 响应相关 (可能需要根据实际 API 返回调整) ---
class QQUserInfo(BaseModel):
    """QQ 用户信息模型 (基于 get_user_info 接口)"""
    ret: int  # 返回码，0表示成功
    msg: str  # 返回消息
    nickname: str | None = None
    figureurl_qq_1: str | None = None  # 40x40 头像
    figureurl_qq_2: str | None = None  # 100x100 头像
    gender: str | None = None
    # ... 可能还有其他字段 ...


# --- 内部使用的模型 ---
class QQUser(BaseModel):
    """我们系统内部存储的 QQ 用户信息"""
    openid: str  # QQ 用户在此应用的唯一标识
    nickname: str | None = None
    avatar_url: str | None = None
    # 可以添加其他应用相关的字段，如绑定时间、内部用户ID等


class QQToken(BaseModel):
    """返回给我们客户端的内部 Token"""
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class QQTokenData(BaseModel):
    """内部 JWT Token 解码后的数据 (Payload)"""
    # 使用 openid 作为用户标识符
    openid: str | None = None
    # 可以添加 purpose 字段区分 access/refresh token
