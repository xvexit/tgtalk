from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, nullable=False)
    tg_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    connection_id: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("chat_id", "tg_message_id", name="uq_messages_chat_tg"),
        CheckConstraint("role IN ('them','owner','bot')", name="ck_messages_role"),
    )


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    persona_id: Mapped[int | None] = mapped_column(Integer)
    overrides: Mapped[str | None] = mapped_column(Text)


class Contact(Base):
    __tablename__ = "contacts"

    chat_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    group_id: Mapped[int | None] = mapped_column(Integer)
    mode: Mapped[str | None] = mapped_column(Text)
    persona_id: Mapped[int | None] = mapped_column(Integer)
    overrides: Mapped[str | None] = mapped_column(Text)


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)


class ReplyLog(Base):
    __tablename__ = "reply_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger_message_id: Mapped[int | None] = mapped_column(Integer)
    mode: Mapped[str | None] = mapped_column(Text)
    reply: Mapped[str | None] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(Text)
    sent: Mapped[bool] = mapped_column(nullable=False, default=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
