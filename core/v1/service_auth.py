from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Form

# 导入配置
from config.providers import SERVICE_CLIENT_ID, SERVICE_CLIENT_SECRET, SERVICE_ACCESS_TOKEN_EXPIRE_MINUTES
# 导入依赖
from core.deps import get_current_service
# 导入模型
from model.mocker.mock_model import ServiceToken, ServiceTokenData
# 导入服务
from service.mocker.mock_token_service import create_service_access_token

router = APIRouter(
    prefix="/service/to/access",
    tags=["Service Authentication (v1)"],  # API 文档中的标签
)


@router.post("/token", response_model=ServiceToken)
async def login_service_for_access_token(
        client_id: Annotated[str, Form()],
        client_secret: Annotated[str, Form()]
):
    """
    客户端凭证流程: 服务使用 Client ID 和 Client Secret 获取 Access Token。
    请求体应为 x-www-form-urlencoded 格式。
    """
    # 1. 验证客户端凭证
    if client_id != SERVICE_CLIENT_ID or client_secret != SERVICE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的客户端凭证",
            headers={"WWW-Authenticate": "Basic"},  # 或 Bearer
        )

    # 2. 定义权限范围 (scopes)
    scopes = ["read:service_data", "write:service_log"]

    # 3. 创建 Access Token
    access_token_expires = timedelta(minutes=SERVICE_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_service_access_token(
        data={"sub": client_id, "scopes": scopes}, expires_delta=access_token_expires
    )

    # 4. 返回 Token
    return ServiceToken(access_token=access_token, token_type="bearer")


@router.get("/data")
async def read_service_data(
        current_service: Annotated[ServiceTokenData, Depends(get_current_service)]
):
    """
    受保护的服务端点，需要有效的服务 Access Token。
    演示 Scope 检查。
    """
    # 检查 Token 是否包含特定 scope
    required_scope = "read:service_data"
    if required_scope not in current_service.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"权限不足，需要 '{required_scope}' scope",
            headers={"WWW-Authenticate": f'Bearer scope="{required_scope}"'},
        )

    return {
        "message": "这是受保护的服务数据",
        "accessed_by_client_id": current_service.client_id,
        "granted_scopes": current_service.scopes
    }
