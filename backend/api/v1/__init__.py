from api.v1.auth import router as auth_router
from api.v1.chat import router as chat_router
from api.v1.sessions import router as session_router
from fastapi import APIRouter

router = APIRouter()
router.include_router(auth_router)
router.include_router(chat_router)
router.include_router(session_router)
