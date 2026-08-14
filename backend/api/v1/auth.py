from api.deps import get_auth_service, get_current_user
from fastapi import APIRouter, Depends
from schemas import (
    AuthResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from services import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthResponse)
async def register_user(
    request: UserRegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    return await auth_service.register_user(request)


@router.post("/login", response_model=AuthResponse)
async def login_user(
    request: UserLoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    return await auth_service.authenticate_user(request)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: UserResponse = Depends(get_current_user),
):
    return current_user
