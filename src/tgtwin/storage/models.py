from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tg_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    connection_id: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sa_text("'live'")
    )

    __table_args__ = (
        UniqueConstraint("chat_id", "tg_message_id", name="uq_messages_chat_tg"),
        CheckConstraint("role IN ('them','owner','bot')", name="ck_messages_role"),
        CheckConstraint("source IN ('live','import')", name="ck_messages_source"),
    )


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    persona_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("personas.id", ondelete="SET NULL")
    )
    overrides: Mapped[dict | None] = mapped_column(JSONB)


class Contact(Base):
    __tablename__ = "contacts"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    group_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("groups.id", ondelete="SET NULL")
    )
    mode: Mapped[str | None] = mapped_column(Text)
    persona_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("personas.id", ondelete="SET NULL")
    )
    overrides: Mapped[dict | None] = mapped_column(JSONB)


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)


class ReplyLog(Base):
    __tablename__ = "reply_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    trigger_message_id: Mapped[int | None] = mapped_column(Integer)
    mode: Mapped[str | None] = mapped_column(Text)
    reply: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict | None] = mapped_column(JSONB)
    sent: Mapped[bool] = mapped_column(nullable=False, default=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Import(Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_hash: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    chats: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("file_hash", "chats", name="uq_imports_file_hash_chats"),
    )
