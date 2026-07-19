"""Bind approvals directly to their idempotent command.

Revision ID: 0003_approval_idempotency
Revises: 0002_tenant_integrity
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0003_approval_idempotency"
down_revision: Optional[str] = "0002_tenant_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _response_payload(value: Any) -> Mapping[str, object]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise RuntimeError("approval idempotency response payload is invalid") from error
    if not isinstance(value, dict):
        raise RuntimeError("approval idempotency response payload is invalid")
    return value


def _backfill_idempotency_keys() -> None:
    connection = op.get_bind()
    metadata = sa.MetaData()
    approvals = sa.Table("approvals", metadata, autoload_with=connection)
    idempotency_records = sa.Table("idempotency_records", metadata, autoload_with=connection)

    keys_by_approval: Dict[tuple[str, str], str] = {}
    records = connection.execute(
        sa.select(
            idempotency_records.c.tenant_id,
            idempotency_records.c.idempotency_key,
            idempotency_records.c.response_payload,
        ).where(idempotency_records.c.operation == "run.approval")
    ).mappings()
    for record in records:
        payload = _response_payload(record["response_payload"])
        run_id = payload.get("run_id")
        key = record["idempotency_key"]
        if not isinstance(run_id, str) or not isinstance(key, str) or not 1 <= len(key) <= 128:
            raise RuntimeError("approval idempotency record cannot be linked safely")
        identity = (str(record["tenant_id"]), run_id)
        if identity in keys_by_approval and keys_by_approval[identity] != key:
            raise RuntimeError("multiple idempotency records reference one approval")
        keys_by_approval[identity] = key

    approval_rows = connection.execute(
        sa.select(approvals.c.approval_id, approvals.c.tenant_id, approvals.c.run_id)
    ).mappings()
    for approval in approval_rows:
        identity = (str(approval["tenant_id"]), str(approval["run_id"]))
        key = keys_by_approval.get(identity)
        if key is None:
            raise RuntimeError("existing approval has no durable idempotency record")
        connection.execute(
            sa.update(approvals)
            .where(approvals.c.approval_id == approval["approval_id"])
            .values(idempotency_key=key)
        )


def upgrade() -> None:
    op.add_column(
        "approvals",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    _backfill_idempotency_keys()
    with op.batch_alter_table("approvals") as batch:
        batch.alter_column(
            "idempotency_key",
            existing_type=sa.String(length=128),
            nullable=False,
        )
        batch.create_unique_constraint(
            "uq_approvals_tenant_idempotency_key",
            ["tenant_id", "idempotency_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("approvals") as batch:
        batch.drop_constraint(
            "uq_approvals_tenant_idempotency_key",
            type_="unique",
        )
        batch.drop_column("idempotency_key")
