from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260604_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_type() -> sa.types.TypeEngine:
    return postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "relay_update_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column("processing_status", sa.String(length=40), nullable=False),
        sa.Column("error_type", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("update_id", name="uq_relay_update_receipts_update_id"),
    )
    op.create_index("ix_relay_update_receipts_update_id", "relay_update_receipts", ["update_id"])

    op.create_table(
        "relay_bots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("bot_token_encrypted", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_bot_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_username", sa.String(length=255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("needs_restart", sa.Boolean(), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('unvalidated', 'valid', 'invalid', 'error')",
            name="ck_relay_bots_status",
        ),
    )
    op.create_index(
        "uq_relay_bots_one_enabled",
        "relay_bots",
        ["enabled"],
        unique=True,
        postgresql_where=sa.text("enabled = true"),
        sqlite_where=sa.text("enabled = 1"),
    )

    op.create_table(
        "relay_private_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=40), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("telegram_user_id", name="uq_relay_private_users_telegram_user_id"),
    )
    op.create_index("ix_relay_private_users_telegram_user_id", "relay_private_users", ["telegram_user_id"])

    op.create_table(
        "llm_providers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider_type", sa.String(length=40), nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("default_model", sa.String(length=255), nullable=False),
        sa.Column("models", _json_type(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "provider_type in ('anthropic', 'openai', 'openai_compatible')",
            name="ck_llm_providers_provider_type",
        ),
        sa.CheckConstraint("timeout_seconds > 0", name="ck_llm_providers_positive_timeout"),
        sa.CheckConstraint("max_retries >= 0", name="ck_llm_providers_nonnegative_retries"),
        sa.CheckConstraint(
            "status in ('unvalidated', 'valid', 'invalid', 'error')",
            name="ck_llm_providers_status",
        ),
    )

    op.create_table(
        "summary_userbots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("api_id", sa.Integer(), nullable=True),
        sa.Column("api_hash_encrypted", sa.Text(), nullable=True),
        sa.Column("phone_number_encrypted", sa.Text(), nullable=True),
        sa.Column("session_encrypted", sa.Text(), nullable=True),
        sa.Column("proxy_url_encrypted", sa.Text(), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_username", sa.String(length=255), nullable=True),
        sa.Column("telegram_display_name", sa.String(length=512), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("auth_status", sa.String(length=40), nullable=False),
        sa.Column("runtime_status", sa.String(length=40), nullable=False),
        sa.Column("last_authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_type", sa.String(length=255), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "auth_status in ('unconfigured', 'code_sent', 'password_required', 'authorized', 'revoked', 'error')",
            name="ck_summary_userbots_auth_status",
        ),
        sa.CheckConstraint(
            "runtime_status in ('stopped', 'starting', 'running', 'reloading', 'failed', 'disabled')",
            name="ck_summary_userbots_runtime_status",
        ),
    )
    op.create_index(
        "uq_summary_userbots_one_enabled",
        "summary_userbots",
        ["enabled"],
        unique=True,
        postgresql_where=sa.text("enabled = true"),
        sqlite_where=sa.text("enabled = 1"),
    )

    op.create_table(
        "relay_private_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("private_user_id", sa.Integer(), nullable=False),
        sa.Column("telegram_update_id", sa.BigInteger(), nullable=True),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("owner_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("owner_message_id", sa.BigInteger(), nullable=True),
        sa.Column("message_type", sa.String(length=40), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("delivery_status", sa.String(length=40), nullable=False),
        sa.Column("error_type", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("direction in ('incoming', 'outgoing')", name="ck_relay_private_messages_direction"),
        sa.ForeignKeyConstraint(["private_user_id"], ["relay_private_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["telegram_update_id"], ["relay_update_receipts.update_id"], ondelete="SET NULL"),
    )
    op.create_index("ix_relay_private_messages_private_user_id", "relay_private_messages", ["private_user_id"])
    op.create_index(
        "uq_relay_private_messages_update_id",
        "relay_private_messages",
        ["telegram_update_id"],
        unique=True,
        postgresql_where=sa.text("telegram_update_id is not null"),
        sqlite_where=sa.text("telegram_update_id is not null"),
    )

    op.create_table(
        "relay_reply_maps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("private_user_id", sa.Integer(), nullable=False),
        sa.Column("private_message_id", sa.Integer(), nullable=True),
        sa.Column("owner_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("owner_message_id", sa.BigInteger(), nullable=False),
        sa.Column("source_kind", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('mapping_pending', 'mapped', 'mapping_failed')",
            name="ck_relay_reply_maps_status",
        ),
        sa.ForeignKeyConstraint(["private_message_id"], ["relay_private_messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["private_user_id"], ["relay_private_users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("owner_chat_id", "owner_message_id", name="uq_relay_reply_maps_owner_message"),
    )

    op.create_table(
        "relay_delivery_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purpose", sa.String(length=80), nullable=False),
        sa.Column("target_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("source_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("source_message_id", sa.BigInteger(), nullable=True),
        sa.Column("result_message_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("error_type", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('pending', 'sent', 'mapped', 'failed')",
            name="ck_relay_delivery_attempts_status",
        ),
    )

    op.create_table(
        "summary_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("llm_provider_id", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "temperature is null or (temperature >= 0 and temperature <= 2)",
            name="ck_summary_profiles_temperature_range",
        ),
        sa.CheckConstraint(
            "max_output_tokens is null or max_output_tokens > 0",
            name="ck_summary_profiles_positive_max_output_tokens",
        ),
        sa.ForeignKeyConstraint(["llm_provider_id"], ["llm_providers.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_summary_profiles_llm_provider_id", "summary_profiles", ["llm_provider_id"])
    op.create_index(
        "uq_summary_profiles_one_default",
        "summary_profiles",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
        sqlite_where=sa.text("is_default = 1"),
    )

    op.create_table(
        "summary_userbot_auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("userbot_id", sa.Integer(), nullable=False),
        sa.Column("phone_code_hash_encrypted", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error_type", sa.String(length=255), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('code_sent', 'password_required', 'completed', 'expired', 'failed')",
            name="ck_summary_userbot_auth_sessions_status",
        ),
        sa.ForeignKeyConstraint(["userbot_id"], ["summary_userbots.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_summary_userbot_auth_sessions_userbot_id", "summary_userbot_auth_sessions", ["userbot_id"])

    op.create_table(
        "summary_entities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("userbot_id", sa.Integer(), nullable=False),
        sa.Column("telegram_entity_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_access_hash", sa.BigInteger(), nullable=True),
        sa.Column("telegram_peer_type", sa.String(length=40), nullable=True),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("collection_status", sa.String(length=40), nullable=False),
        sa.Column("summary_profile_id", sa.Integer(), nullable=True),
        sa.Column("interval_minutes", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_type", sa.String(length=255), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "entity_type in ('group', 'supergroup', 'megagroup', 'broadcast_channel', 'unknown')",
            name="ck_summary_entities_entity_type",
        ),
        sa.CheckConstraint(
            "collection_status in ('disabled', 'active', 'paused', 'error')",
            name="ck_summary_entities_collection_status",
        ),
        sa.CheckConstraint(
            "interval_minutes is null or interval_minutes > 0",
            name="ck_summary_entities_positive_interval",
        ),
        sa.ForeignKeyConstraint(["summary_profile_id"], ["summary_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["userbot_id"], ["summary_userbots.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("userbot_id", "telegram_entity_id", name="uq_summary_entities_userbot_entity"),
    )
    op.create_index("ix_summary_entities_summary_profile_id", "summary_entities", ["summary_profile_id"])
    op.create_index("ix_summary_entities_userbot_id", "summary_entities", ["userbot_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=True),
        sa.Column("redacted_before", _json_type(), nullable=True),
        sa.Column("redacted_after", _json_type(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "summary_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("userbot_id", sa.Integer(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_thread_id", sa.BigInteger(), nullable=True),
        sa.Column("source_kind", sa.String(length=40), nullable=False),
        sa.Column("message_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edited_after_summary_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sender_user_id", sa.BigInteger(), nullable=True),
        sa.Column("sender_username", sa.String(length=255), nullable=True),
        sa.Column("sender_display_name", sa.String(length=512), nullable=True),
        sa.Column("message_type", sa.String(length=40), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("summary_content", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(length=512), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("media_metadata", _json_type(), nullable=True),
        sa.CheckConstraint(
            "source_kind in ('telethon_update', 'future_backfill')",
            name="ck_summary_messages_source_kind",
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["summary_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["userbot_id"], ["summary_userbots.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("entity_id", "telegram_message_id", name="uq_summary_messages_entity_message"),
    )
    op.create_index("ix_summary_messages_entity_id", "summary_messages", ["entity_id"])
    op.create_index("ix_summary_messages_userbot_id", "summary_messages", ["userbot_id"])
    op.create_index("ix_summary_messages_entity_sequence", "summary_messages", ["entity_id", "id"])
    op.create_index("ix_summary_messages_entity_date", "summary_messages", ["entity_id", "message_date"])

    op.create_table(
        "summary_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("last_summary_sequence", sa.Integer(), nullable=False),
        sa.Column("last_summary_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["summary_entities.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("entity_id", name="uq_summary_states_entity_id"),
    )

    op.create_table(
        "summary_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("starting_sequence", sa.Integer(), nullable=False),
        sa.Column("cutoff_sequence", sa.Integer(), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("llm_provider_id", sa.Integer(), nullable=True),
        sa.Column("summary_profile_id", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_type", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('pending', 'running', 'succeeded', 'failed', 'blocked')",
            name="ck_summary_jobs_status",
        ),
        sa.CheckConstraint("trigger_type in ('manual', 'scheduled')", name="ck_summary_jobs_trigger_type"),
        sa.ForeignKeyConstraint(["entity_id"], ["summary_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["llm_provider_id"], ["llm_providers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["summary_profile_id"], ["summary_profiles.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_summary_jobs_entity_id", "summary_jobs", ["entity_id"])
    op.create_index(
        "uq_summary_jobs_one_active_per_entity",
        "summary_jobs",
        ["entity_id"],
        unique=True,
        sqlite_where=sa.text("status in ('pending', 'running')"),
        postgresql_where=sa.text("status in ('pending', 'running')"),
    )

    op.create_table(
        "summary_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("llm_provider_id", sa.Integer(), nullable=True),
        sa.Column("summary_profile_id", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("interval_start_sequence", sa.Integer(), nullable=False),
        sa.Column("interval_end_sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["summary_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["summary_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["llm_provider_id"], ["llm_providers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["summary_profile_id"], ["summary_profiles.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("job_id", name="uq_summary_results_job_id"),
    )
    op.create_index("ix_summary_results_entity_id", "summary_results", ["entity_id"])

    op.create_table(
        "summary_delivery_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("summary_result_id", sa.Integer(), nullable=False),
        sa.Column("relay_bot_id", sa.Integer(), nullable=True),
        sa.Column("target_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("sent_chunks", sa.Integer(), nullable=False),
        sa.Column("telegram_message_ids", _json_type(), nullable=True),
        sa.Column("error_type", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('pending', 'running', 'succeeded', 'failed', 'skipped', 'timeout')",
            name="ck_summary_delivery_attempts_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_summary_delivery_attempts_nonnegative_attempt_count"),
        sa.CheckConstraint("max_attempts > 0", name="ck_summary_delivery_attempts_positive_max_attempts"),
        sa.CheckConstraint("timeout_seconds > 0", name="ck_summary_delivery_attempts_positive_timeout"),
        sa.CheckConstraint("total_chunks >= 0", name="ck_summary_delivery_attempts_nonnegative_total_chunks"),
        sa.CheckConstraint("sent_chunks >= 0", name="ck_summary_delivery_attempts_nonnegative_sent_chunks"),
        sa.ForeignKeyConstraint(["relay_bot_id"], ["relay_bots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["summary_result_id"], ["summary_results.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_summary_delivery_attempts_summary_result_id", "summary_delivery_attempts", ["summary_result_id"])


def downgrade() -> None:
    op.drop_index("ix_summary_delivery_attempts_summary_result_id", table_name="summary_delivery_attempts")
    op.drop_table("summary_delivery_attempts")
    op.drop_index("ix_summary_results_entity_id", table_name="summary_results")
    op.drop_table("summary_results")
    op.drop_index("uq_summary_jobs_one_active_per_entity", table_name="summary_jobs")
    op.drop_index("ix_summary_jobs_entity_id", table_name="summary_jobs")
    op.drop_table("summary_jobs")
    op.drop_table("summary_states")
    op.drop_index("ix_summary_messages_entity_date", table_name="summary_messages")
    op.drop_index("ix_summary_messages_entity_sequence", table_name="summary_messages")
    op.drop_index("ix_summary_messages_userbot_id", table_name="summary_messages")
    op.drop_index("ix_summary_messages_entity_id", table_name="summary_messages")
    op.drop_table("summary_messages")
    op.drop_table("audit_logs")
    op.drop_index("ix_summary_entities_userbot_id", table_name="summary_entities")
    op.drop_index("ix_summary_entities_summary_profile_id", table_name="summary_entities")
    op.drop_table("summary_entities")
    op.drop_index("ix_summary_userbot_auth_sessions_userbot_id", table_name="summary_userbot_auth_sessions")
    op.drop_table("summary_userbot_auth_sessions")
    op.drop_index("uq_summary_profiles_one_default", table_name="summary_profiles")
    op.drop_index("ix_summary_profiles_llm_provider_id", table_name="summary_profiles")
    op.drop_table("summary_profiles")
    op.drop_table("relay_delivery_attempts")
    op.drop_table("relay_reply_maps")
    op.drop_index("uq_relay_private_messages_update_id", table_name="relay_private_messages")
    op.drop_index("ix_relay_private_messages_private_user_id", table_name="relay_private_messages")
    op.drop_table("relay_private_messages")
    op.drop_index("uq_summary_userbots_one_enabled", table_name="summary_userbots")
    op.drop_table("summary_userbots")
    op.drop_table("llm_providers")
    op.drop_index("ix_relay_private_users_telegram_user_id", table_name="relay_private_users")
    op.drop_table("relay_private_users")
    op.drop_index("uq_relay_bots_one_enabled", table_name="relay_bots")
    op.drop_table("relay_bots")
    op.drop_index("ix_relay_update_receipts_update_id", table_name="relay_update_receipts")
    op.drop_table("relay_update_receipts")
