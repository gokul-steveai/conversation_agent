from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from models import Base


class SessionModel(Base):
    __tablename__ = "chat_sessions"

    session_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    state_json = Column(Text, nullable=False)
    messages_json = Column(Text, nullable=False)
    history_json = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("UserModel", back_populates="chat_sessions")
