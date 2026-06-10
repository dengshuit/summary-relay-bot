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
        "telegram_updates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column("payload", _json_type(), nullable=True),
        sa.Column("processing_status", sa.String(length=40), nullable=False),
        sa.Column("error_type", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_retained", sa.Boolean(), nullable=False),
        sa.Column("payload_redacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("update_id", name="uq_telegram_updates_update_id"),
    )
    op.create_index("ix_telegram_updates_update_id", "telegram_updates", ["update_id"])

    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("summaries_enabled", sa.Boolean(), nullable=False),
        sa.Column("summary_interval_minutes", sa.Integer(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("chat_type in ('group', 'supergroup')", name="ck_groups_chat_type"),
        sa.CheckConstraint(
            "summary_interval_minutes is null or summary_interval_minutes > 0",
            name="ck_groups_positive_interval",
        ),
        sa.UniqueConstraint("chat_id", name="uq_groups_chat_id"),
    )
    op.create_index("ix_groups_chat_id", "groups", ["chat_id"])

    op.create_table(
        "private_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=40), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("telegram_user_id", name="uq_private_users_telegram_user_id"),
    )
    op.create_index("ix_private_users_telegram_user_id", "private_users", ["telegram_user_id"])

    op.create_table(
        "group_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("raw_update_id", sa.Integer(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("sender_user_id", sa.BigInteger(), nullable=True),
        sa.Column("sender_display_name", sa.String(length=512), nullable=True),
        sa.Column("message_type", sa.String(length=40), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("summary_content", sa.Text(), nullable=False),
        sa.Column("file_id", sa.String(length=512), nullable=True),
        sa.Column("file_unique_id", sa.String(length=512), nullable=True),
        sa.Column("file_name", sa.String(length=512), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("media_metadata", _json_type(), nullable=True),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["raw_update_id"], ["telegram_updates.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("group_id", "telegram_message_id", name="uq_group_messages_group_message"),
    )
    op.create_index("ix_group_messages_group_id", "group_messages", ["group_id"])
    op.create_index("ix_group_messages_group_sequence", "group_messages", ["group_id", "id"])

    op.create_table(
        "private_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("private_user_id", sa.Integer(), nullable=False),
        sa.Column("raw_update_id", sa.Integer(), nullable=True),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("admin_message_id", sa.BigInteger(), nullable=True),
        sa.Column("message_type", sa.String(length=40), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("delivery_status", sa.String(length=40), nullable=False),
        sa.Column("error_type", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("direction in ('incoming', 'outgoing')", name="ck_private_messages_direction"),
        sa.ForeignKeyConstraint(["private_user_id"], ["private_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["raw_update_id"], ["telegram_updates.id"], ondelete="RESTRICT"),
    )

    op.create_table(
        "admin_reply_maps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("private_user_id", sa.Integer(), nullable=False),
        sa.Column("private_message_id", sa.Integer(), nullable=True),
        sa.Column("admin_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("admin_message_id", sa.BigInteger(), nullable=False),
        sa.Column("source_kind", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('mapping_pending', 'mapped', 'mapping_failed')",
            name="ck_reply_map_status",
        ),
        sa.ForeignKeyConstraint(["private_message_id"], ["private_messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["private_user_id"], ["private_users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("admin_chat_id", "admin_message_id", name="uq_admin_reply_maps_admin_message"),
    )

    op.create_table(
        "summary_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("last_summary_sequence", sa.Integer(), nullable=False),
        sa.Column("last_summary_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("chat_id", name="uq_summary_state_chat_id"),
        sa.UniqueConstraint("group_id", name="uq_summary_state_group_id"),
    )
    op.create_index("ix_summary_state_chat_id", "summary_state", ["chat_id"])

    op.create_table(
        "bot_instances",
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
            name="ck_bot_instances_status",
        ),
    )
    op.create_index(
        "uq_bot_instances_one_enabled",
        "bot_instances",
        ["enabled"],
        unique=True,
        postgresql_where=sa.text("enabled = true"),
        sqlite_where=sa.text("enabled = 1"),
    )

    op.create_table(
        "llm_providers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider_type", sa.String(length=40), nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("default_model", sa.String(length=255), nullable=False),
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
        "group_summary_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("summary_profile_id", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("interval_minutes > 0", name="ck_group_summary_settings_positive_interval"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["summary_profile_id"], ["summary_profiles.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("group_id", name="uq_group_summary_settings_group_id"),
    )
    op.create_index(
        "ix_group_summary_settings_summary_profile_id",
        "group_summary_settings",
        ["summary_profile_id"],
    )

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
        "summary_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
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
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["llm_provider_id"], ["llm_providers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["summary_profile_id"], ["summary_profiles.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_summary_jobs_chat_id", "summary_jobs", ["chat_id"])
    op.create_index("ix_summary_jobs_group_id", "summary_jobs", ["group_id"])
    op.create_index(
        "uq_summary_jobs_one_running_per_group",
        "summary_jobs",
        ["group_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )

    op.create_table(
        "summary_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("delivered_admin_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("delivered_message_id", sa.BigInteger(), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("llm_provider_id", sa.Integer(), nullable=True),
        sa.Column("summary_profile_id", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("interval_start_sequence", sa.Integer(), nullable=False),
        sa.Column("interval_end_sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["summary_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["llm_provider_id"], ["llm_providers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["summary_profile_id"], ["summary_profiles.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("job_id", name="uq_summary_results_job_id"),
    )

    op.create_table(
        "delivery_attempts",
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
        sa.CheckConstraint("status in ('pending', 'sent', 'mapped', 'failed')", name="ck_delivery_attempts_status"),
    )


def downgrade() -> None:
    op.drop_table("delivery_attempts")
    op.drop_table("summary_results")
    op.drop_index("uq_summary_jobs_one_running_per_group", table_name="summary_jobs")
    op.drop_index("ix_summary_jobs_group_id", table_name="summary_jobs")
    op.drop_index("ix_summary_jobs_chat_id", table_name="summary_jobs")
    op.drop_table("summary_jobs")
    op.drop_table("audit_logs")
    op.drop_index("ix_group_summary_settings_summary_profile_id", table_name="group_summary_settings")
    op.drop_table("group_summary_settings")
    op.drop_index("uq_summary_profiles_one_default", table_name="summary_profiles")
    op.drop_index("ix_summary_profiles_llm_provider_id", table_name="summary_profiles")
    op.drop_table("summary_profiles")
    op.drop_table("llm_providers")
    op.drop_index("uq_bot_instances_one_enabled", table_name="bot_instances")
    op.drop_table("bot_instances")
    op.drop_index("ix_summary_state_chat_id", table_name="summary_state")
    op.drop_table("summary_state")
    op.drop_table("admin_reply_maps")
    op.drop_table("private_messages")
    op.drop_index("ix_group_messages_group_sequence", table_name="group_messages")
    op.drop_index("ix_group_messages_group_id", table_name="group_messages")
    op.drop_table("group_messages")
    op.drop_index("ix_private_users_telegram_user_id", table_name="private_users")
    op.drop_table("private_users")
    op.drop_index("ix_groups_chat_id", table_name="groups")
    op.drop_table("groups")
    op.drop_index("ix_telegram_updates_update_id", table_name="telegram_updates")
    op.drop_table("telegram_updates")
