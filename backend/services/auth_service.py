import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from config import settings
from pydantic import ValidationError
from repositories import UserRepository
from schemas import (
    AuthResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from utils import format_validation_error, logger


class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"), hashed_password.encode("utf-8")
            )
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    @staticmethod
    def create_access_token(user_id: str, email: str, name: str) -> str:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=settings.jwt_expiration_minutes)
        payload = {
            "sub": user_id,
            "email": email,
            "name": name,
            "iat": now,
            "exp": expires_at,
        }
        token = jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        return token

    @staticmethod
    def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT Token has expired.")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT Token: {e}")
            return None

    @classmethod
    async def register_user(cls, request: UserRegisterRequest) -> AuthResponse:
        try:
            email = request.email.strip().lower()
            name = request.name.strip()

            existing = await UserRepository.find_by_email(email)
            if existing:
                return AuthResponse(
                    success=False,
                    error=f"An account with email '{email}' already exists.",
                )

            password_hash = cls.hash_password(request.password)
            user_id = str(uuid.uuid4())

            user = await UserRepository.create_user(
                user_id=user_id,
                name=name,
                email=email,
                password_hash=password_hash,
            )

            token = cls.create_access_token(
                user_id=user.id, email=user.email, name=user.name
            )
            user_resp = UserResponse(
                user_id=user.id,
                name=user.name,
                email=user.email,
            )
            return AuthResponse(success=True, token=token, user=user_resp)
        except ValidationError as val_err:
            return AuthResponse(success=False, error=format_validation_error(val_err))
        except Exception as e:
            logger.error(f"Error during registration: {e}")
            return AuthResponse(success=False, error="An internal error occurred.")

    @classmethod
    async def authenticate_user(cls, request: UserLoginRequest) -> AuthResponse:
        try:
            email = request.email.strip().lower()
            user = await UserRepository.find_by_email(email)
            if not user:
                return AuthResponse(success=False, error="Invalid email or password.")

            if not cls.verify_password(request.password, user.password_hash):
                return AuthResponse(success=False, error="Invalid email or password.")

            token = cls.create_access_token(
                user_id=user.id, email=user.email, name=user.name
            )
            user_resp = UserResponse(
                user_id=user.id,
                name=user.name,
                email=user.email,
            )
            return AuthResponse(success=True, token=token, user=user_resp)
        except ValidationError as val_err:
            return AuthResponse(success=False, error=format_validation_error(val_err))
        except Exception as e:
            logger.error(f"Error during login authentication: {e}")
            return AuthResponse(success=False, error="An internal error occurred.")
