from __future__ import annotations

from datetime import datetime, date

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    JSON,
    func,
    Date,
    Float,
)

from .db import Base


# --------------------------------------------------
# User
# --------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # 🔐 NEW
    password_hash: Mapped[str] = mapped_column(String(255))

    name: Mapped[str | None] = mapped_column(String(120))
    nickname: Mapped[str | None] = mapped_column(String(120))
    age: Mapped[int | None] = mapped_column(Integer)
    hobbies: Mapped[str | None] = mapped_column(Text)
    diagnosis: Mapped[str | None] = mapped_column(Text)

    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    memories: Mapped[list["Memory"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    moods: Mapped[list["Mood"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


# --------------------------------------------------
# Conversation
# --------------------------------------------------
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id_fk: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        order_by="Message.created_at",
        cascade="all, delete-orphan",
    )


# --------------------------------------------------
# Message
# --------------------------------------------------
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)

    role: Mapped[str] = mapped_column(String(16))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    annotations: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


# --------------------------------------------------
# Memory (long-term user facts)
# --------------------------------------------------
class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id_fk: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    key: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="memories")


# --------------------------------------------------
# Mood tracking
# --------------------------------------------------
class Mood(Base):
    __tablename__ = "moods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id_fk: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    mood: Mapped[str] = mapped_column(String(32), index=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    day: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="moods")
