from fastapi import APIRouter
from core.v1 import code_to_access, service_auth


router = APIRouter(prefix="/v1")

router.include_router(code_to_access.router)
router.include_router(service_auth.router)
