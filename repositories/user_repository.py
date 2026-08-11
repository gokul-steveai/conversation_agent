from typing import Optional

from sqlalchemy import select

from core.database import get_db
from models.user import UserModel
from utils.logger import logger


class UserRepository:
    @classmethod
    async def find_by_id(cls, user_id: str) -> Optional[UserModel]:
        async with get_db() as db:
            result = await db.execute(select(UserModel).filter(UserModel.id == user_id))
            return result.scalars().first()

    @classmethod
    async def find_by_email(cls, email: str) -> Optional[UserModel]:
        async with get_db() as db:
            result = await db.execute(
                select(UserModel).filter(UserModel.email == email.strip().lower())
            )
            return result.scalars().first()

    @classmethod
    async def create_user(
        cls,
        user_id: str,
        name: str,
        email: str,
        password_hash: str,
    ) -> UserModel:
        async with get_db() as db:
            user = UserModel(
                id=user_id,
                name=name.strip(),
                email=email.strip().lower(),
                password_hash=password_hash,
                is_active=True,
            )
            db.add(user)
            logger.info(
                f"Created new registered user record: {user.email} (ID: {user_id})"
            )
            return user

    @classmethod
    async def get_or_create_user(
        cls,
        user_id: str,
        name: str = "Default User",
        email: str = "user@example.com",
    ) -> UserModel:
        async with get_db() as db:
            result = await db.execute(select(UserModel).filter(UserModel.id == user_id))
            user = result.scalars().first()
            if not user:
                user = UserModel(
                    id=user_id,
                    name=name,
                    email=email.lower(),
                    password_hash="placeholder_hash",
                    is_active=True,
                )
                db.add(user)
                logger.info(f"Created default user record: {user_id}")
            return user
