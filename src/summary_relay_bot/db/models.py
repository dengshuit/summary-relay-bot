from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from summary_relay_bot.db.base import Base


MAX_SHORT_TEXT = 255


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TelegramUpdate(Base):
    __tablename__ = "telegram_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    update_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    processing_status: Mapped[str] = mapped_column(String(40), nullable=False, default="raw_persisted")
    error_type: Mapped[str | None] = mapped_column(String(MAX_SHORT_TEXT))
    error_message: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload_retained: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    payload_redacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    group_messages: Mapped[list["GroupMessage"]] = relationship(back_populates="raw_update")
    private_messages: Mapped[list["PrivateMessage"]] = relationship(back_populates="raw_update")


class GroupChat(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    chat_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512))
    username: Mapped[str | None] = mapped_column(String(255))
    summaries_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    summary_interval_minutes: Mapped[int | None] = mapped_column(Integer)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    messages: Mapped[list["GroupMessage"]] = relationship(back_populates="group")
    summary_state: Mapped["SummaryState | None"] = relationship(back_populates="group", uselist=False)
    summary_jobs: Mapped[list["SummaryJob"]] = relationship(back_populates="group")

    __table_args__ = (
        CheckConstraint("chat_type in ('group', 'supergroup')", name="ck_groups_chat_type"),
        CheckConstraint(
            "summary_interval_minutes is null or summary_interval_minutes > 0",
            name="ck_groups_positive_interval",
        ),
    )


class GroupMessage(Base):
    __tablename__ = "group_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_update_id: Mapped[int] = mapped_column(ForeignKey("telegram_updates.id", ondelete="RESTRICT"), nullable=False)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sender_user_id: Mapped[int | None] = mapped_column(BigInteger)
    sender_display_name: Mapped[str | None] = mapped_column(String(512))
    message_type: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    summary_content: Mapped[str] = mapped_column(Text, nullable=False)
    file_id: Mapped[str | None] = mapped_column(String(512))
    file_unique_id: Mapped[str | None] = mapped_column(String(512))
    file_name: Mapped[str | None] = mapped_column(String(512))
    mime_type: Mapped[str | None] = mapped_column(String(255))
    file_size: Mapped[int | None] = mapped_column(Integer)
    media_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    group: Mapped[GroupChat] = relationship(back_populates="messages")
    raw_update: Mapped[TelegramUpdate] = relationship(back_populates="group_messages")

    __table_args__ = (
        UniqueConstraint("group_id", "telegram_message_id", name="uq_group_messages_group_message"),
        Index("ix_group_messages_group_sequence", "group_id", "id"),
    )


class PrivateUser(Base):
    __tablename__ = "private_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str | None] = mapped_column(String(40))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    messages: Mapped[list["PrivateMessage"]] = relationship(back_populates="private_user")
    reply_maps: Mapped[list["AdminReplyMap"]] = relationship(back_populates="private_user")


class PrivateMessage(Base):
    __tablename__ = "private_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    private_user_id: Mapped[int] = mapped_column(ForeignKey("private_users.id", ondelete="CASCADE"), nullable=False)
    raw_update_id: Mapped[int | None] = mapped_column(ForeignKey("telegram_updates.id", ondelete="RESTRICT"))
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    admin_message_id: Mapped[int | None] = mapped_column(BigInteger)
    message_type: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    delivery_status: Mapped[str] = mapped_column(String(40), nullable=False, default="stored")
    error_type: Mapped[str | None] = mapped_column(String(MAX_SHORT_TEXT))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    private_user: Mapped[PrivateUser] = relationship(back_populates="messages")
    raw_update: Mapped[TelegramUpdate | None] = relationship(back_populates="private_messages")
    reply_maps: Mapped[list["AdminReplyMap"]] = relationship(back_populates="private_message")

    __table_args__ = (
        CheckConstraint("direction in ('incoming', 'outgoing')", name="ck_private_messages_direction"),
    )


class AdminReplyMap(Base):
    __tablename__ = "admin_reply_maps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    private_user_id: Mapped[int] = mapped_column(ForeignKey("private_users.id", ondelete="CASCADE"), nullable=False)
    private_message_id: Mapped[int | None] = mapped_column(ForeignKey("private_messages.id", ondelete="SET NULL"))
    admin_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    admin_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="mapped")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    private_user: Mapped[PrivateUser] = relationship(back_populates="reply_maps")
    private_message: Mapped[PrivateMessage | None] = relationship(back_populates="reply_maps")

    __table_args__ = (
        UniqueConstraint("admin_chat_id", "admin_message_id", name="uq_admin_reply_maps_admin_message"),
        CheckConstraint("status in ('mapping_pending', 'mapped', 'mapping_failed')", name="ck_reply_map_status"),
    )


class SummaryState(Base):
    __tablename__ = "summary_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, unique=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    last_summary_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_summary_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    group: Mapped[GroupChat] = relationship(back_populates="summary_state")


class SummaryJob(Base):
    __tablename__ = "summary_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    starting_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cutoff_sequence: Mapped[int | None] = mapped_column(Integer)
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_type: Mapped[str | None] = mapped_column(String(MAX_SHORT_TEXT))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    group: Mapped[GroupChat] = relationship(back_populates="summary_jobs")
    result: Mapped["SummaryResult | None"] = relationship(back_populates="job", uselist=False)

    __table_args__ = (
        CheckConstraint(
            "status in ('pending', 'running', 'succeeded', 'failed', 'blocked')",
            name="ck_summary_jobs_status",
        ),
        CheckConstraint(
            "trigger_type in ('manual', 'scheduled')",
            name="ck_summary_jobs_trigger_type",
        ),
        Index(
            "uq_summary_jobs_one_running_per_group",
            "group_id",
            unique=True,
            sqlite_where=text("status = 'running'"),
            postgresql_where=text("status = 'running'"),
        ),
    )


class SummaryResult(Base):
    __tablename__ = "summary_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("summary_jobs.id", ondelete="CASCADE"), nullable=False, unique=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    delivered_admin_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    delivered_message_id: Mapped[int | None] = mapped_column(BigInteger)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    interval_start_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    interval_end_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    job: Mapped[SummaryJob] = relationship(back_populates="result")


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purpose: Mapped[str] = mapped_column(String(80), nullable=False)
    target_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    source_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    source_message_id: Mapped[int | None] = mapped_column(BigInteger)
    result_message_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    error_type: Mapped[str | None] = mapped_column(String(MAX_SHORT_TEXT))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        CheckConstraint("status in ('pending', 'sent', 'mapped', 'failed')", name="ck_delivery_attempts_status"),
    )
