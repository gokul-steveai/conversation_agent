from sqlalchemy import Column, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SessionModel(Base):
    """SQLAlchemy Database ORM Model for persisting conversation sessions."""

    __tablename__ = "sessions"

    session_id = Column(String(64), primary_key=True)
    title = Column(String(255), nullable=False)
    state_json = Column(Text, nullable=False)
    messages_json = Column(Text, nullable=False)
    history_json = Column(Text, nullable=False)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)
