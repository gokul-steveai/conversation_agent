from typing import Optional

from models import UserModel
from repositories.base_repository import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from utils import logger


class UserRepository(BaseRepository[UserModel]):
    def __init__(self, db_session: AsyncSession):
        super().__init__(db_session=db_session, model_cls=UserModel)

    async def find_by_email(self, email: str) -> Optional[UserModel]:
        result = await self._session.execute(
            select(UserModel).filter(UserModel.email == email.strip().lower())
        )
        return result.scalars().first()

    async def create_user(
        self,
        user_id: str,
        name: str,
        email: str,
        password_hash: str,
    ) -> UserModel:
        user = UserModel(
            id=user_id,
            name=name.strip(),
            email=email.strip().lower(),
            password_hash=password_hash,
            is_active=True,
        )
        await self.create_entity(user)
        logger.info(f"Created new registered user record: {user.email} (ID: {user_id})")
        return user

    async def get_or_create_user(
        self,
        user_id: str,
        name: str = "Default User",
        email: str = "user@example.com",
    ) -> UserModel:
        user = await self.find_by_id(user_id)
        if not user:
            user = UserModel(
                id=user_id,
                name=name,
                email=email.lower(),
                password_hash="placeholder_hash",
                is_active=True,
            )
            await self.create_entity(user)
            logger.info(f"Created default user record: {user_id}")
        return user
