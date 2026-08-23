"""Initial schema: users, monitors, checks.

Revision ID: 001_initial
Revises:
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Enum("USER", "ADMIN", name="user_role", native_enum=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "monitors",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column(
            "method",
            sa.Enum("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", name="http_method", native_enum=False),
            nullable=False,
        ),
        sa.Column("expected_status_code", sa.Integer(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("timeout_ms", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("UP", "DOWN", "PENDING", "UNKNOWN", name="monitor_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("last_latency_ms", sa.Integer(), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("consecutive_failure_count", sa.Integer(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("monitors_enabled_idx", "monitors", ["enabled"], unique=False)
    op.create_index("monitors_next_check_idx", "monitors", ["enabled", "next_check_at"], unique=False)
    op.create_index("monitors_user_id_idx", "monitors", ["user_id"], unique=False)

    op.create_table(
        "checks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("monitor_id", sa.UUID(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column(
            "error_type",
            sa.Enum(
                "TIMEOUT",
                "CONNECTION",
                "DNS",
                "SSL",
                "STATUS_CODE",
                "INVALID_URL",
                "UNKNOWN",
                name="check_error_type",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id"], ["monitors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "checks_monitor_id_checked_at_idx",
        "checks",
        ["monitor_id", sa.text("checked_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("checks_monitor_id_checked_at_idx", table_name="checks")
    op.drop_table("checks")
    op.drop_index("monitors_user_id_idx", table_name="monitors")
    op.drop_index("monitors_next_check_idx", table_name="monitors")
    op.drop_index("monitors_enabled_idx", table_name="monitors")
    op.drop_table("monitors")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
