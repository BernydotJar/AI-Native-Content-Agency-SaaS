from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class TenantRow(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PrincipalRow(Base):
    __tablename__ = "principals"

    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), primary_key=True
    )
    principal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    auth_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MissionRow(Base):
    __tablename__ = "missions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("mission_id", "tenant_id", name="uq_missions_id_tenant"),
        CheckConstraint("budget_cents >= 0", name="budget_nonnegative"),
    )

    mission_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(String(500), nullable=False)
    platforms: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    budget_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_asset: Mapped[str] = mapped_column(String(1000), nullable=False)
    campaign_goal: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class RunRow(Base):
    __tablename__ = "runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mission_id", "tenant_id"],
            ["missions.mission_id", "missions.tenant_id"],
            name="fk_runs_mission_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint("run_id", "tenant_id", name="uq_runs_id_tenant"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mission_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    artifact_manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    external_side_effects: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class RunStepRow(Base):
    __tablename__ = "run_steps"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "tenant_id"],
            ["runs.run_id", "runs.tenant_id"],
            name="fk_run_steps_run_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint("run_id", "role", name="uq_run_steps_run_role"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="progress_range"),
    )

    step_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ArtifactRow(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "tenant_id"],
            ["runs.run_id", "runs.tenant_id"],
            name="fk_artifacts_run_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint("run_id", "ordinal", name="uq_artifacts_run_ordinal"),
    )

    artifact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    created_by: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[Dict[str, object]] = mapped_column(JSON, nullable=False)
    evidence_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ToolEvidenceRow(Base):
    __tablename__ = "tool_evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "tenant_id"],
            ["runs.run_id", "runs.tenant_id"],
            name="fk_tool_evidence_run_tenant",
            ondelete="CASCADE",
        ),
    )

    run_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        nullable=False,
        index=True,
    )
    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tool: Mapped[str] = mapped_column(String(120), nullable=False)
    operation: Mapped[str] = mapped_column(String(120), nullable=False)
    sandbox: Mapped[bool] = mapped_column(Boolean, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Dict[str, object]] = mapped_column(JSON, nullable=False)
    references: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RunEventRow(Base):
    __tablename__ = "run_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "tenant_id"],
            ["runs.run_id", "runs.tenant_id"],
            name="fk_run_events_run_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint("run_id", "sequence", name="uq_run_events_sequence"),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    evidence_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False)


class ApprovalRow(Base):
    __tablename__ = "approvals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "tenant_id"],
            ["runs.run_id", "runs.tenant_id"],
            name="fk_approvals_run_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            name="fk_approvals_principal_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("run_id", name="uq_approvals_run_id"),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_approvals_tenant_idempotency_key",
        ),
    )

    approval_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    principal_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(160), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "tenant_id"],
            ["runs.run_id", "runs.tenant_id"],
            name="fk_audit_events_run_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            name="fk_audit_events_principal_tenant",
            ondelete="RESTRICT",
        ),
    )

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    principal_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[Dict[str, object]] = mapped_column(JSON, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IdempotencyRow(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_idempotency_key"),)

    record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    operation: Mapped[str] = mapped_column(String(120), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_payload: Mapped[Dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
