from typing import AsyncContextManager, Callable, List, Optional

from core.database import get_db
from models.memory import (
    AgentContextSummaryModel,
    AgentConversationalHistoryModel,
    AgentToolExecutionLogModel,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


class MemoryRepository:
    def __init__(
        self,
        session_factory: Optional[
            Callable[[], AsyncContextManager[AsyncSession]]
        ] = None,
    ) -> None:
        self.session_factory = session_factory or get_db

    async def save_conversational_history(
        self, entry: AgentConversationalHistoryModel
    ) -> str:
        async with self.session_factory() as session:
            session.add(entry)
            await session.commit()
        return entry.id

    async def mark_messages_summarized(
        self, thread_id: str, summary_id: str, message_ids: Optional[List[str]] = None
    ) -> None:
        if message_ids:
            stmt = (
                update(AgentConversationalHistoryModel)
                .where(
                    AgentConversationalHistoryModel.thread_id == thread_id,
                    AgentConversationalHistoryModel.id.in_(message_ids),
                    AgentConversationalHistoryModel.summary_id.is_(None),
                )
                .values(summary_id=summary_id)
            )
        else:
            stmt = (
                update(AgentConversationalHistoryModel)
                .where(
                    AgentConversationalHistoryModel.thread_id == thread_id,
                    AgentConversationalHistoryModel.summary_id.is_(None),
                )
                .values(summary_id=summary_id)
            )
        async with self.session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def save_tool_execution_log(
        self, log_entry: AgentToolExecutionLogModel
    ) -> str:
        async with self.session_factory() as session:
            session.add(log_entry)
            await session.commit()
        return log_entry.id

    async def get_tool_execution_logs(
        self, thread_id: str, limit: int = 20
    ) -> List[AgentToolExecutionLogModel]:
        stmt = (
            select(AgentToolExecutionLogModel)
            .where(AgentToolExecutionLogModel.thread_id == thread_id)
            .order_by(AgentToolExecutionLogModel.timestamp.desc())
            .limit(limit)
        )
        async with self.session_factory() as session:
            res = await session.execute(stmt)
            return list(res.scalars().all())

    async def save_context_summary(
        self, summary_entry: AgentContextSummaryModel
    ) -> str:
        async with self.session_factory() as session:
            session.add(summary_entry)
            await session.commit()
        return summary_entry.id

    async def get_context_summary_by_id(
        self, summary_id: str
    ) -> Optional[AgentContextSummaryModel]:
        stmt = select(AgentContextSummaryModel).where(
            AgentContextSummaryModel.id == summary_id
        )
        async with self.session_factory() as session:
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    async def get_unsummarized_messages(
        self, thread_id: str
    ) -> List[AgentConversationalHistoryModel]:
        stmt = (
            select(AgentConversationalHistoryModel)
            .where(
                AgentConversationalHistoryModel.thread_id == thread_id,
                AgentConversationalHistoryModel.summary_id.is_(None),
            )
            .order_by(AgentConversationalHistoryModel.timestamp.asc())
        )
        async with self.session_factory() as session:
            res = await session.execute(stmt)
            return list(res.scalars().all())

    async def get_recent_unsummarized_messages(
        self, thread_id: str, limit: int = 10
    ) -> List[AgentConversationalHistoryModel]:
        stmt = (
            select(AgentConversationalHistoryModel)
            .where(
                AgentConversationalHistoryModel.thread_id == thread_id,
                AgentConversationalHistoryModel.summary_id.is_(None),
            )
            .order_by(AgentConversationalHistoryModel.timestamp.desc())
            .limit(limit)
        )
        async with self.session_factory() as session:
            res = await session.execute(stmt)
            entries = list(res.scalars().all())
            return list(reversed(entries))

    async def get_messages_by_summary_id(
        self, summary_id: str
    ) -> List[AgentConversationalHistoryModel]:
        stmt = (
            select(AgentConversationalHistoryModel)
            .where(AgentConversationalHistoryModel.summary_id == summary_id)
            .order_by(AgentConversationalHistoryModel.timestamp.asc())
        )
        async with self.session_factory() as session:
            res = await session.execute(stmt)
            return list(res.scalars().all())
