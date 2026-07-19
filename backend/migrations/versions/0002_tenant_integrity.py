"""Enforce tenant identity through every relational edge.

Revision ID: 0002_tenant_integrity
Revises: 0001_control_plane
"""

from typing import Optional, Sequence, Union

from alembic import op


revision: str = "0002_tenant_integrity"
down_revision: Optional[str] = "0001_control_plane"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RUN_CHILDREN = {
    "run_steps": ("fk_run_steps_run_id_runs", "fk_run_steps_run_tenant"),
    "artifacts": ("fk_artifacts_run_id_runs", "fk_artifacts_run_tenant"),
    "tool_evidence": ("fk_tool_evidence_run_id_runs", "fk_tool_evidence_run_tenant"),
    "run_events": ("fk_run_events_run_id_runs", "fk_run_events_run_tenant"),
    "approvals": ("fk_approvals_run_id_runs", "fk_approvals_run_tenant"),
    "audit_events": ("fk_audit_events_run_id_runs", "fk_audit_events_run_tenant"),
}


def upgrade() -> None:
    with op.batch_alter_table("missions") as batch:
        batch.create_unique_constraint(
            "uq_missions_id_tenant",
            ["mission_id", "tenant_id"],
        )

    with op.batch_alter_table("runs") as batch:
        batch.drop_constraint("fk_runs_mission_id_missions", type_="foreignkey")
        batch.create_unique_constraint("uq_runs_id_tenant", ["run_id", "tenant_id"])
        batch.create_foreign_key(
            "fk_runs_mission_tenant",
            "missions",
            ["mission_id", "tenant_id"],
            ["mission_id", "tenant_id"],
            ondelete="CASCADE",
        )

    for table, (old_name, new_name) in RUN_CHILDREN.items():
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(old_name, type_="foreignkey")
            batch.create_foreign_key(
                new_name,
                "runs",
                ["run_id", "tenant_id"],
                ["run_id", "tenant_id"],
                ondelete="CASCADE",
            )

    with op.batch_alter_table("approvals") as batch:
        batch.create_foreign_key(
            "fk_approvals_principal_tenant",
            "principals",
            ["tenant_id", "principal_id"],
            ["tenant_id", "principal_id"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table("audit_events") as batch:
        batch.create_foreign_key(
            "fk_audit_events_principal_tenant",
            "principals",
            ["tenant_id", "principal_id"],
            ["tenant_id", "principal_id"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table("idempotency_records") as batch:
        batch.create_foreign_key(
            "fk_idempotency_records_tenant_id_tenants",
            "tenants",
            ["tenant_id"],
            ["tenant_id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("idempotency_records") as batch:
        batch.drop_constraint(
            "fk_idempotency_records_tenant_id_tenants",
            type_="foreignkey",
        )

    with op.batch_alter_table("audit_events") as batch:
        batch.drop_constraint("fk_audit_events_principal_tenant", type_="foreignkey")

    with op.batch_alter_table("approvals") as batch:
        batch.drop_constraint("fk_approvals_principal_tenant", type_="foreignkey")

    for table, (old_name, new_name) in reversed(tuple(RUN_CHILDREN.items())):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(new_name, type_="foreignkey")
            batch.create_foreign_key(
                old_name,
                "runs",
                ["run_id"],
                ["run_id"],
                ondelete="CASCADE",
            )

    with op.batch_alter_table("runs") as batch:
        batch.drop_constraint("fk_runs_mission_tenant", type_="foreignkey")
        batch.drop_constraint("uq_runs_id_tenant", type_="unique")
        batch.create_foreign_key(
            "fk_runs_mission_id_missions",
            "missions",
            ["mission_id"],
            ["mission_id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("missions") as batch:
        batch.drop_constraint("uq_missions_id_tenant", type_="unique")
