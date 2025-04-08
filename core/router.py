from fastapi import APIRouter

from core.v1 import code_to_access, service_auth, qq_auth

router = APIRouter()

api_v1_router = APIRouter(prefix="/v1")
api_v1_router.include_router(code_to_access.router)
api_v1_router.include_router(service_auth.router)
api_v1_router.include_router(qq_auth.router)

router.include_router(api_v1_router, prefix="/oauth")
