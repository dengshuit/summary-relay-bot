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
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text as sa_text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from summary_relay_bot.db.base import Base


MAX_SHORT_TEXT = 255


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RelayUpdateReceipt(Base):
    """Temporary relay-domain update receipt for old Bot API ingestion paths."""

    __tablename__ = "relay_update_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    update_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    processing_status: Mapped[str] = mapped_column(String(40), nullable=False, default="raw_persisted")
    error_type: Mapped[str | None] = mapped_column(String(MAX_SHORT_TEXT))
    error_message: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    private_messages: Mapped[list["RelayPrivateMessage"]] = relationship(back_populates="raw_update")

    @property
    def payload(self) -> None:
        return None

    @payload.setter
    def payload(self, _value: Any) -> None:
        return None

    @property
    def payload_retained(self) -> bool:
        return False

    @payload_retained.setter
    def payload_retained(self, _value: bool) -> None:
        return None

    @property
    def payload_redacted_at(self) -> None:
        return None

    @payload_redacted_at.setter
    def payload_redacted_at(self, _value: datetime | None) -> None:
        return None


class RelayBot(Base):
    __tablename__ = "relay_bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    bot_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_bot_id: Mapped[int | None] = mapped_column(BigInteger)
    telegram_username: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="unvalidated")
    needs_restart: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        CheckConstraint(
            "status in ('unvalidated', 'valid', 'invalid', 'error')",
            name="ck_relay_bots_status",
        ),
        Index(
            "uq_relay_bots_one_enabled",
            "enabled",
            unique=True,
            sqlite_where=sa_text("enabled = 1"),
            postgresql_where=sa_text("enabled = true"),
        ),
    )


class RelayPrivateUser(Base):
    __tablename__ = "relay_private_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str | None] = mapped_column(String(40))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    messages: Mapped[list["RelayPrivateMessage"]] = relationship(back_populates="private_user")
    reply_maps: Mapped[list["RelayReplyMap"]] = relationship(back_populates="private_user")


class RelayPrivateMessage(Base):
    __tablename__ = "relay_private_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    private_user_id: Mapped[int] = mapped_column(
        ForeignKey("relay_private_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_update_id: Mapped[int | None] = mapped_column(
        "telegram_update_id",
        BigInteger,
        ForeignKey("relay_update_receipts.update_id", ondelete="SET NULL"),
    )
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    owner_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    admin_message_id: Mapped[int | None] = mapped_column("owner_message_id", BigInteger)
    message_type: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    delivery_status: Mapped[str] = mapped_column(String(40), nullable=False, default="stored")
    error_type: Mapped[str | None] = mapped_column(String(MAX_SHORT_TEXT))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    private_user: Mapped[RelayPrivateUser] = relationship(back_populates="messages")
    raw_update: Mapped[RelayUpdateReceipt | None] = relationship(back_populates="private_messages")
    reply_maps: Mapped[list["RelayReplyMap"]] = relationship(back_populates="private_message")

    telegram_update_id = synonym("raw_update_id")
    owner_message_id = synonym("admin_message_id")

    __table_args__ = (
        CheckConstraint("direction in ('incoming', 'outgoing')", name="ck_relay_private_messages_direction"),
        Index(
            "uq_relay_private_messages_update_id",
            "telegram_update_id",
            unique=True,
            sqlite_where=sa_text("telegram_update_id is not null"),
            postgresql_where=sa_text("telegram_update_id is not null"),
        ),
    )


class RelayReplyMap(Base):
    __tablename__ = "relay_reply_maps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    private_user_id: Mapped[int] = mapped_column(
        ForeignKey("relay_private_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    private_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("relay_private_messages.id", ondelete="SET NULL")
    )
    admin_chat_id: Mapped[int] = mapped_column("owner_chat_id", BigInteger, nullable=False)
    admin_message_id: Mapped[int] = mapped_column("owner_message_id", BigInteger, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="mapped")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    private_user: Mapped[RelayPrivateUser] = relationship(back_populates="reply_maps")
    private_message: Mapped[RelayPrivateMessage | None] = relationship(back_populates="reply_maps")

    owner_chat_id = synonym("admin_chat_id")
    owner_message_id = synonym("admin_message_id")

    __table_args__ = (
        UniqueConstraint("owner_chat_id", "owner_message_id", name="uq_relay_reply_maps_owner_message"),
        CheckConstraint(
            "status in ('mapping_pending', 'mapped', 'mapping_failed')",
            name="ck_relay_reply_maps_status",
        ),
    )


class RelayDeliveryAttempt(Base):
    __tablename__ = "relay_delivery_attempts"

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
        CheckConstraint(
            "status in ('pending', 'sent', 'mapped', 'failed')",
            name="ck_relay_delivery_attempts_status",
        ),
    )


class LLMProvider(Base):
    __tablename__ = "llm_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(1024))
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    default_model: Mapped[str] = mapped_column(String(255), nullable=False)
    models: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="unvalidated")
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    summary_profiles: Mapped[list["SummaryProfile"]] = relationship(back_populates="llm_provider")

    __table_args__ = (
        CheckConstraint(
            "provider_type in ('anthropic', 'openai', 'openai_compatible')",
            name="ck_llm_providers_provider_type",
        ),
        CheckConstraint("timeout_seconds > 0", name="ck_llm_providers_positive_timeout"),
        CheckConstraint("max_retries >= 0", name="ck_llm_providers_nonnegative_retries"),
        CheckConstraint(
            "status in ('unvalidated', 'valid', 'invalid', 'error')",
            name="ck_llm_providers_status",
        ),
    )


class SummaryProfile(Base):
    __tablename__ = "summary_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    llm_provider_id: Mapped[int] = mapped_column(
        ForeignKey("llm_providers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    model: Mapped[str | None] = mapped_column(String(255))
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False, default="v1")
    system_prompt: Mapped[str | None] = mapped_column(Text)
    temperature: Mapped[float | None] = mapped_column(Float)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    llm_provider: Mapped[LLMProvider] = relationship(back_populates="summary_profiles")
    summary_entities: Mapped[list["SummaryEntity"]] = relationship(back_populates="summary_profile")
    group_settings = synonym("summary_entities")

    __table_args__ = (
        CheckConstraint(
            "temperature is null or (temperature >= 0 and temperature <= 2)",
            name="ck_summary_profiles_temperature_range",
        ),
        CheckConstraint(
            "max_output_tokens is null or max_output_tokens > 0",
            name="ck_summary_profiles_positive_max_output_tokens",
        ),
        Index(
            "uq_summary_profiles_one_default",
            "is_default",
            unique=True,
            sqlite_where=sa_text("is_default = 1"),
            postgresql_where=sa_text("is_default = true"),
        ),
    )


class SummaryUserbot(Base):
    __tablename__ = "summary_userbots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="default")
    api_id: Mapped[int | None] = mapped_column(Integer)
    api_hash_encrypted: Mapped[str | None] = mapped_column(Text)
    phone_number_encrypted: Mapped[str | None] = mapped_column(Text)
    session_encrypted: Mapped[str | None] = mapped_column(Text)
    proxy_url_encrypted: Mapped[str | None] = mapped_column(Text)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)
    telegram_username: Mapped[str | None] = mapped_column(String(255))
    telegram_display_name: Mapped[str | None] = mapped_column(String(512))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auth_status: Mapped[str] = mapped_column(String(40), nullable=False, default="unconfigured")
    runtime_status: Mapped[str] = mapped_column(String(40), nullable=False, default="stopped")
    last_authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_type: Mapped[str | None] = mapped_column(String(MAX_SHORT_TEXT))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    auth_sessions: Mapped[list["SummaryUserbotAuthSession"]] = relationship(back_populates="userbot")
    entities: Mapped[list["SummaryEntity"]] = relationship(back_populates="userbot")
    messages: Mapped[list["SummaryMessage"]] = relationship(back_populates="userbot")

    __table_args__ = (
        CheckConstraint(
            "auth_status in ('unconfigured', 'code_sent', 'password_required', 'authorized', 'revoked', 'error')",
            name="ck_summary_userbots_auth_status",
        ),
        CheckConstraint(
            "runtime_status in ('stopped', 'starting', 'running', 'reloading', 'failed', 'disabled')",
            name="ck_summary_userbots_runtime_status",
        ),
        Index(
            "uq_summary_userbots_one_enabled",
            "enabled",
            unique=True,
            sqlite_where=sa_text("enabled = 1"),
            postgresql_where=sa_text("enabled = true"),
        ),
    )


class SummaryUserbotAuthSession(Base):
    __tablename__ = "summary_userbot_auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    userbot_id: Mapped[int] = mapped_column(
        ForeignKey("summary_userbots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phone_code_hash_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="code_sent")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_error_type: Mapped[str | None] = mapped_column(String(MAX_SHORT_TEXT))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    userbot: Mapped[SummaryUserbot] = relationship(back_populates="auth_sessions")

    __table_args__ = (
        CheckConstraint(
            "status in ('code_sent', 'password_required', 'completed', 'expired', 'failed')",
            name="ck_summary_userbot_auth_sessions_status",
        ),
    )


class SummaryEntity(Base):
    __tablename__ = "summary_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    userbot_id: Mapped[int] = mapped_column(
        ForeignKey("summary_userbots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chat_id: Mapped[int] = mapped_column("telegram_entity_id", BigInteger, nullable=False)
    telegram_access_hash: Mapped[int | None] = mapped_column(BigInteger)
    telegram_peer_type: Mapped[str | None] = mapped_column(String(40))
    chat_type: Mapped[str] = mapped_column("entity_type", String(40), nullable=False, default="unknown")
    title: Mapped[str | None] = mapped_column(String(512))
    username: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    collection_status: Mapped[str] = mapped_column(String(40), nullable=False, default="disabled")
    summary_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("summary_profiles.id", ondelete="SET NULL"),
        index=True,
    )
    interval_minutes: Mapped[int | None] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="UTC")
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_type: Mapped[str | None] = mapped_column(String(MAX_SHORT_TEXT))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    userbot: Mapped[SummaryUserbot] = relationship(back_populates="entities")
    messages: Mapped[list["SummaryMessage"]] = relationship(back_populates="group")
    summary_state: Mapped["SummaryState | None"] = relationship(back_populates="group", uselist=False)
    summary_jobs: Mapped[list["SummaryJob"]] = relationship(back_populates="group")
    summary_profile: Mapped[SummaryProfile | None] = relationship(back_populates="summary_entities")

    telegram_entity_id = synonym("chat_id")
    entity_type = synonym("chat_type")
    group_id = synonym("id")

    @property
    def summary_settings(self) -> SummaryEntity | None:
        if self.enabled or self.interval_minutes is not None or self.summary_profile_id is not None:
            return self
        return None

    @summary_settings.setter
    def summary_settings(self, _value: Any) -> None:
        return None

    @property
    def group(self) -> SummaryEntity:
        return self

    @group.setter
    def group(self, value: SummaryEntity) -> None:
        self.id = value.id

    __table_args__ = (
        UniqueConstraint("userbot_id", "telegram_entity_id", name="uq_summary_entities_userbot_entity"),
        CheckConstraint(
            "entity_type in ('group', 'supergroup', 'megagroup', 'broadcast_channel', 'unknown')",
            name="ck_summary_entities_entity_type",
        ),
        CheckConstraint(
            "collection_status in ('disabled', 'active', 'paused', 'error')",
            name="ck_summary_entities_collection_status",
        ),
        CheckConstraint(
            "interval_minutes is null or interval_minutes > 0",
            name="ck_summary_entities_positive_interval",
        ),
    )


class SummaryMessage(Base):
    __tablename__ = "summary_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        "entity_id",
        ForeignKey("summary_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    userbot_id: Mapped[int] = mapped_column(
        ForeignKey("summary_userbots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_thread_id: Mapped[int | None] = mapped_column(BigInteger)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="telethon_update")
    message_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stored_at: Mapped[datetime] = mapped_column("collected_at", DateTime(timezone=True), nullable=False, default=utcnow)
    edited_after_summary_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sender_user_id: Mapped[int | None] = mapped_column(BigInteger)
    sender_username: Mapped[str | None] = mapped_column(String(255))
    sender_display_name: Mapped[str | None] = mapped_column(String(512))
    message_type: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    summary_content: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(512))
    mime_type: Mapped[str | None] = mapped_column(String(255))
    file_size: Mapped[int | None] = mapped_column(Integer)
    media_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    group: Mapped[SummaryEntity] = relationship(back_populates="messages")
    userbot: Mapped[SummaryUserbot] = relationship(back_populates="messages")

    entity_id = synonym("group_id")
    collected_at = synonym("stored_at")

    @property
    def file_id(self) -> str | None:
        value = (self.media_metadata or {}).get("file_id")
        return str(value) if value is not None else None

    @file_id.setter
    def file_id(self, value: str | None) -> None:
        metadata = dict(self.media_metadata or {})
        if value is None:
            metadata.pop("file_id", None)
        else:
            metadata["file_id"] = value
        self.media_metadata = metadata or None

    @property
    def file_unique_id(self) -> str | None:
        value = (self.media_metadata or {}).get("file_unique_id")
        return str(value) if value is not None else None

    @file_unique_id.setter
    def file_unique_id(self, value: str | None) -> None:
        metadata = dict(self.media_metadata or {})
        if value is None:
            metadata.pop("file_unique_id", None)
        else:
            metadata["file_unique_id"] = value
        self.media_metadata = metadata or None

    __table_args__ = (
        UniqueConstraint("entity_id", "telegram_message_id", name="uq_summary_messages_entity_message"),
        CheckConstraint(
            "source_kind in ('telethon_update', 'future_backfill')",
            name="ck_summary_messages_source_kind",
        ),
        Index("ix_summary_messages_entity_sequence", "entity_id", "id"),
        Index("ix_summary_messages_entity_date", "entity_id", "message_date"),
    )


class SummaryState(Base):
    __tablename__ = "summary_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        "entity_id",
        ForeignKey("summary_entities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    last_summary_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_summary_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    group: Mapped[SummaryEntity] = relationship(back_populates="summary_state")
    entity_id = synonym("group_id")

    @property
    def chat_id(self) -> int | None:
        return self.group.chat_id if self.group is not None else None

    @chat_id.setter
    def chat_id(self, _value: int | None) -> None:
        return None


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(120))
    redacted_before: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    redacted_after: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class SummaryJob(Base):
    __tablename__ = "summary_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        "entity_id",
        ForeignKey("summary_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    starting_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cutoff_sequence: Mapped[int | None] = mapped_column(Integer)
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    llm_provider_id: Mapped[int | None] = mapped_column(ForeignKey("llm_providers.id", ondelete="SET NULL"))
    summary_profile_id: Mapped[int | None] = mapped_column(ForeignKey("summary_profiles.id", ondelete="SET NULL"))
    model: Mapped[str | None] = mapped_column(String(255))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_type: Mapped[str | None] = mapped_column(String(MAX_SHORT_TEXT))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    group: Mapped[SummaryEntity] = relationship(back_populates="summary_jobs")
    result: Mapped["SummaryResult | None"] = relationship(back_populates="job", uselist=False)
    entity_id = synonym("group_id")

    @property
    def chat_id(self) -> int | None:
        return self.group.chat_id if self.group is not None else None

    @chat_id.setter
    def chat_id(self, _value: int | None) -> None:
        return None

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
            "uq_summary_jobs_one_active_per_entity",
            "entity_id",
            unique=True,
            sqlite_where=sa_text("status in ('pending', 'running')"),
            postgresql_where=sa_text("status in ('pending', 'running')"),
        ),
    )


class SummaryResult(Base):
    __tablename__ = "summary_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("summary_jobs.id", ondelete="CASCADE"), nullable=False, unique=True)
    group_id: Mapped[int] = mapped_column(
        "entity_id",
        ForeignKey("summary_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    llm_provider_id: Mapped[int | None] = mapped_column(ForeignKey("llm_providers.id", ondelete="SET NULL"))
    summary_profile_id: Mapped[int | None] = mapped_column(ForeignKey("summary_profiles.id", ondelete="SET NULL"))
    model: Mapped[str | None] = mapped_column(String(255))
    interval_start_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    interval_end_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    job: Mapped[SummaryJob] = relationship(back_populates="result")
    entity_id = synonym("group_id")

    @property
    def delivered_admin_chat_id(self) -> None:
        return None

    @delivered_admin_chat_id.setter
    def delivered_admin_chat_id(self, _value: int | None) -> None:
        return None

    @property
    def delivered_message_id(self) -> None:
        return None

    @delivered_message_id.setter
    def delivered_message_id(self, _value: int | None) -> None:
        return None


class SummaryDeliveryAttempt(Base):
    __tablename__ = "summary_delivery_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    summary_result_id: Mapped[int] = mapped_column(
        ForeignKey("summary_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relay_bot_id: Mapped[int | None] = mapped_column(ForeignKey("relay_bots.id", ondelete="SET NULL"))
    target_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    telegram_message_ids: Mapped[list[int] | None] = mapped_column(JSON)
    error_type: Mapped[str | None] = mapped_column(String(MAX_SHORT_TEXT))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    result: Mapped[SummaryResult] = relationship()
    relay_bot: Mapped[RelayBot | None] = relationship()

    __table_args__ = (
        CheckConstraint(
            "status in ('pending', 'running', 'succeeded', 'failed', 'skipped', 'timeout')",
            name="ck_summary_delivery_attempts_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_summary_delivery_attempts_nonnegative_attempt_count"),
        CheckConstraint("max_attempts > 0", name="ck_summary_delivery_attempts_positive_max_attempts"),
        CheckConstraint("timeout_seconds > 0", name="ck_summary_delivery_attempts_positive_timeout"),
        CheckConstraint("total_chunks >= 0", name="ck_summary_delivery_attempts_nonnegative_total_chunks"),
        CheckConstraint("sent_chunks >= 0", name="ck_summary_delivery_attempts_nonnegative_sent_chunks"),
    )


# Temporary compatibility aliases for the first schema-reset child. Later child
# tasks should migrate services and tests to the relay/summary domain names and
# remove these aliases.
TelegramUpdate = RelayUpdateReceipt
BotInstance = RelayBot
PrivateUser = RelayPrivateUser
PrivateMessage = RelayPrivateMessage
AdminReplyMap = RelayReplyMap
DeliveryAttempt = RelayDeliveryAttempt
GroupChat = SummaryEntity
GroupMessage = SummaryMessage
GroupSummarySettings = SummaryEntity
