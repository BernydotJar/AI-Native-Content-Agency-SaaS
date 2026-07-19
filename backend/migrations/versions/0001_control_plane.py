"""Create the durable control-plane schema.

Revision ID: 0001_control_plane
Revises: None
"""

from typing import Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0001_control_plane"
down_revision: Optional[str] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", name=op.f("pk_tenants")),
    )
    op.create_table(
        "principals",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("principal_id", sa.String(length=64), nullable=False),
        sa.Column("auth_mode", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.tenant_id"], name=op.f("fk_principals_tenant_id_tenants"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("tenant_id", "principal_id", name=op.f("pk_principals")),
    )
    op.create_table(
        "missions",
        sa.Column("mission_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(length=500), nullable=False),
        sa.Column("platforms", sa.JSON(), nullable=False),
        sa.Column("budget_cents", sa.Integer(), nullable=False),
        sa.Column("source_asset", sa.String(length=1000), nullable=False),
        sa.Column("campaign_goal", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("budget_cents >= 0", name=op.f("ck_missions_budget_nonnegative")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["principals.tenant_id", "principals.principal_id"],
            name=op.f("fk_missions_tenant_id_principals"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("mission_id", name=op.f("pk_missions")),
    )
    op.create_index(op.f("ix_missions_tenant_id"), "missions", ["tenant_id"], unique=False)
    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("mission_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("artifact_manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("external_side_effects", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("version >= 1", name=op.f("ck_runs_version_positive")),
        sa.ForeignKeyConstraint(
            ["mission_id"], ["missions.mission_id"], name=op.f("fk_runs_mission_id_missions"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.tenant_id"], name=op.f("fk_runs_tenant_id_tenants"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_runs")),
    )
    op.create_index(op.f("ix_runs_status"), "runs", ["status"], unique=False)
    op.create_index(op.f("ix_runs_tenant_id"), "runs", ["tenant_id"], unique=False)
    op.create_table(
        "run_steps",
        sa.Column("step_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name=op.f("ck_run_steps_progress_range")),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.run_id"], name=op.f("fk_run_steps_run_id_runs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("step_id", name=op.f("pk_run_steps")),
        sa.UniqueConstraint("run_id", "role", name="uq_run_steps_run_role"),
    )
    op.create_index(op.f("ix_run_steps_run_id"), "run_steps", ["run_id"], unique=False)
    op.create_index(op.f("ix_run_steps_tenant_id"), "run_steps", ["tenant_id"], unique=False)
    op.create_table(
        "artifacts",
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("created_by", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.run_id"], name=op.f("fk_artifacts_run_id_runs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("artifact_id", name=op.f("pk_artifacts")),
        sa.UniqueConstraint("run_id", "ordinal", name="uq_artifacts_run_ordinal"),
    )
    op.create_index(op.f("ix_artifacts_run_id"), "artifacts", ["run_id"], unique=False)
    op.create_index(op.f("ix_artifacts_tenant_id"), "artifacts", ["tenant_id"], unique=False)
    op.create_table(
        "tool_evidence",
        sa.Column("evidence_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("tool", sa.String(length=120), nullable=False),
        sa.Column("operation", sa.String(length=120), nullable=False),
        sa.Column("sandbox", sa.Boolean(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("references", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.run_id"], name=op.f("fk_tool_evidence_run_id_runs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("run_id", "evidence_id", name=op.f("pk_tool_evidence")),
    )
    op.create_index(op.f("ix_tool_evidence_run_id"), "tool_evidence", ["run_id"], unique=False)
    op.create_index(op.f("ix_tool_evidence_tenant_id"), "tool_evidence", ["tenant_id"], unique=False)
    op.create_table(
        "run_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("artifact_ids", sa.JSON(), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.run_id"], name=op.f("fk_run_events_run_id_runs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_run_events")),
        sa.UniqueConstraint("run_id", "sequence", name="uq_run_events_sequence"),
    )
    op.create_index(op.f("ix_run_events_run_id"), "run_events", ["run_id"], unique=False)
    op.create_index(op.f("ix_run_events_tenant_id"), "run_events", ["tenant_id"], unique=False)
    op.create_table(
        "approvals",
        sa.Column("approval_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("principal_id", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("reviewer", sa.String(length=160), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("artifact_manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.run_id"], name=op.f("fk_approvals_run_id_runs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("approval_id", name=op.f("pk_approvals")),
        sa.UniqueConstraint("run_id", name="uq_approvals_run_id"),
    )
    op.create_index(op.f("ix_approvals_tenant_id"), "approvals", ["tenant_id"], unique=False)
    op.create_table(
        "audit_events",
        sa.Column("audit_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("principal_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.run_id"], name=op.f("fk_audit_events_run_id_runs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("audit_id", name=op.f("pk_audit_events")),
    )
    op.create_index(op.f("ix_audit_events_run_id"), "audit_events", ["run_id"], unique=False)
    op.create_index(op.f("ix_audit_events_tenant_id"), "audit_events", ["tenant_id"], unique=False)
    op.create_table(
        "idempotency_records",
        sa.Column("record_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=120), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("record_id", name=op.f("pk_idempotency_records")),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_idempotency_key"),
    )
    op.create_index(
        op.f("ix_idempotency_records_tenant_id"), "idempotency_records", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_idempotency_records_tenant_id"), table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_index(op.f("ix_audit_events_tenant_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_run_id"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index(op.f("ix_approvals_tenant_id"), table_name="approvals")
    op.drop_table("approvals")
    op.drop_index(op.f("ix_run_events_tenant_id"), table_name="run_events")
    op.drop_index(op.f("ix_run_events_run_id"), table_name="run_events")
    op.drop_table("run_events")
    op.drop_index(op.f("ix_tool_evidence_tenant_id"), table_name="tool_evidence")
    op.drop_index(op.f("ix_tool_evidence_run_id"), table_name="tool_evidence")
    op.drop_table("tool_evidence")
    op.drop_index(op.f("ix_artifacts_tenant_id"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_run_id"), table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index(op.f("ix_run_steps_tenant_id"), table_name="run_steps")
    op.drop_index(op.f("ix_run_steps_run_id"), table_name="run_steps")
    op.drop_table("run_steps")
    op.drop_index(op.f("ix_runs_tenant_id"), table_name="runs")
    op.drop_index(op.f("ix_runs_status"), table_name="runs")
    op.drop_table("runs")
    op.drop_index(op.f("ix_missions_tenant_id"), table_name="missions")
    op.drop_table("missions")
    op.drop_table("principals")
    op.drop_table("tenants")
