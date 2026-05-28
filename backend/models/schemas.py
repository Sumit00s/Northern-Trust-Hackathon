"""
Pydantic models for the IMS domain.
Covers: Signals, Alerts, Incidents, Notifications, Audit Logs, API responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ─── Enums ────────────────────────────────────────────────────────

class ComponentType(str, Enum):
    RDBMS = "RDBMS"
    CACHE = "CACHE"
    API = "API"
    MCP = "MCP"
    QUEUE = "QUEUE"
    NOSQL = "NOSQL"
    NETWORK = "NETWORK"
    SERVER = "SERVER"


class Severity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    OPEN = "OPEN"  # Legacy support


class IncidentType(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"


class RootCauseCategory(str, Enum):
    INFRASTRUCTURE = "Infrastructure"
    CODE_BUG = "Code Bug"
    CONFIGURATION = "Configuration"
    EXTERNAL_DEPENDENCY = "External Dependency"
    CAPACITY = "Capacity"
    NETWORK = "Network"
    UNKNOWN = "Unknown"


# ─── Alert Payload (New simplified format from simulator) ──────────

class AlertPayload(BaseModel):
    """Simplified alert format from monitoring tools / simulator."""
    type: str = Field(..., examples=["infrastructure", "application"])
    severity: str = Field(..., examples=["P1", "P2", "P3", "P4"])
    service: str = Field(..., examples=["web-server-01", "checkout-api"])
    message: str = Field(..., examples=["CPU usage at 98% for 5 minutes"])
    source: str = Field(default="unknown", examples=["prometheus", "datadog"])

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v not in ("infrastructure", "application"):
            raise ValueError("type must be 'infrastructure' or 'application'")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v):
        if v not in ("P1", "P2", "P3", "P4"):
            raise ValueError("severity must be P1, P2, P3, or P4")
        return v


# ─── Signal (incoming from producers — legacy format) ─────────────

class SignalPayload(BaseModel):
    """Raw signal ingested from monitored infrastructure."""
    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    component_id: str = Field(..., examples=["CACHE_CLUSTER_01", "RDBMS_PRIMARY"])
    component_type: ComponentType
    error_type: str = Field(..., examples=["TIMEOUT", "CONNECTION_REFUSED", "OOM"])
    message: str = Field(..., examples=["Connection pool exhausted"])
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_ip: str = Field(default="0.0.0.0")
    latency_ms: float | None = None


class SignalBatch(BaseModel):
    """Batch of signals for bulk ingestion."""
    signals: list[SignalPayload] = Field(..., min_length=1, max_length=1000)


# ─── Work Item ────────────────────────────────────────────────────

class WorkItemCreate(BaseModel):
    component_id: str
    component_type: ComponentType
    severity: Severity
    title: str
    signal_count: int = 1
    first_signal_at: datetime
    last_signal_at: datetime


class WorkItemResponse(BaseModel):
    id: str
    component_id: str
    component_type: str
    severity: str
    status: str
    title: str
    signal_count: int
    first_signal_at: datetime
    last_signal_at: datetime
    assigned_to: str | None = None
    created_at: datetime
    updated_at: datetime


class WorkItemTransition(BaseModel):
    target_status: IncidentStatus

    @field_validator("target_status")
    @classmethod
    def validate_target(cls, v):
        if v not in IncidentStatus:
            raise ValueError(f"Invalid status: {v}")
        return v


# ─── Incident Response (Full format for new API) ─────────────────

class IncidentResponse(BaseModel):
    id: str
    incident_type: str
    severity: str
    status: str
    service: str | None = None
    message_text: str | None = None
    source: str | None = None
    title: str
    signal_count: int
    assigned_to: str | None = None
    escalation_count: int = 0
    resolution_note: str | None = None
    created_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    # Also include legacy fields for compatibility
    component_id: str
    component_type: str
    first_signal_at: datetime
    last_signal_at: datetime


class ResolveRequest(BaseModel):
    resolution_note: str = Field(..., min_length=5, description="Describe how the incident was resolved")


# ─── Notification ─────────────────────────────────────────────────

class NotificationResponse(BaseModel):
    id: str
    incident_id: str
    email_to: str
    subject: str
    body: str
    sent_at: datetime
    type: str
    status: str


# ─── Audit Log ────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: str
    incident_id: str
    action: str
    old_status: str | None = None
    new_status: str | None = None
    performed_by: str
    timestamp: datetime
    notes: str | None = None


# ─── RCA ──────────────────────────────────────────────────────────

class RCASubmission(BaseModel):
    """Root Cause Analysis — all fields mandatory."""
    incident_start: datetime
    incident_end: datetime
    root_cause_category: RootCauseCategory
    root_cause_detail: str = Field(..., min_length=10)
    fix_applied: str = Field(..., min_length=10)
    prevention_steps: str = Field(..., min_length=10)

    @field_validator("incident_end")
    @classmethod
    def end_after_start(cls, v, info):
        if "incident_start" in info.data and v <= info.data["incident_start"]:
            raise ValueError("incident_end must be after incident_start")
        return v


class RCAResponse(BaseModel):
    id: str
    work_item_id: str
    incident_start: datetime
    incident_end: datetime
    root_cause_category: str
    root_cause_detail: str
    fix_applied: str
    prevention_steps: str
    mttr_seconds: int
    submitted_at: datetime


# ─── Dashboard & Health ───────────────────────────────────────────

class DashboardState(BaseModel):
    total_open: int = 0
    total_investigating: int = 0
    total_resolved: int = 0
    total_closed: int = 0
    signals_per_sec: float = 0.0
    avg_mttr_seconds: float = 0.0
    active_incidents: list[WorkItemResponse] = []


class HealthResponse(BaseModel):
    status: str = "healthy"
    uptime_seconds: float
    signals_per_sec: float
    queue_depth: int
    pg_pool_size: int
    pg_pool_free: int