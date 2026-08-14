from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AgentConversationalHistoryModel(Base):
    __tablename__ = "agent_conversational_history"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(
        "metadata", Text, nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    summary_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, default=None
    )


class AgentToolExecutionLogModel(Base):
    __tablename__ = "agent_tool_execution_logs"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tool_call_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    tool_args: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_preview: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="success", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(
        "metadata", Text, nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class BaseVectorModel(Base):
    __abstract__ = True

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str] = mapped_column("metadata", Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class AgentKnowledgeBaseVectorModel(BaseVectorModel):
    __tablename__ = "agent_knowledge_base_vectors"


class AgentWorkflowPatternModel(BaseVectorModel):
    __tablename__ = "agent_workflow_patterns"


class AgentToolboxDefinitionModel(BaseVectorModel):
    __tablename__ = "agent_toolbox_definitions"


class AgentEntitiesRegistryModel(BaseVectorModel):
    __tablename__ = "agent_entities_registry"


class AgentContextSummaryModel(BaseVectorModel):
    __tablename__ = "agent_context_summaries"
