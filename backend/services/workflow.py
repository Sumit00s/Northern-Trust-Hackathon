"""
Workflow Service - Incident State Machine & Severity Assignment

This module implements:
1. State Pattern: Full lifecycle (DETECTED → ACKNOWLEDGED → INVESTIGATING → RESOLVED → CLOSED)
2. Strategy Pattern: Component-type-based severity assignment (P0-P4)
3. Alert ingestion: Creates incidents from AlertPayload
4. RCA Validation: Mandatory resolution note before closing
5. MTTR Calculation: Automatic Mean Time To Resolution calculation
6. Audit Logging: Every state change logged with timestamp
7. Email Notifications: Sent on incident creation and state changes
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from models.schemas import (
    IncidentStatus, SignalPayload, Severity, ComponentType, RCASubmission,
    AlertPayload, IncidentType
)
from db.database import get_pg
from services.classifier import classify_alert

logger = logging.getLogger("ims.workflow")


# ============================================================================
# STRATEGY PATTERN: Component-Type → Severity Mapping
# ============================================================================

class AlertStrategy(ABC):
    @abstractmethod
    def evaluate(self, component_type: ComponentType, error_type: str) -> Severity:
        pass


class RDBMSAlertStrategy(AlertStrategy):
    def evaluate(self, component_type: ComponentType, error_type: str) -> Severity:
        critical_errors = {"CONNECTION_REFUSED", "OOM", "DATA_CORRUPTION"}
        if error_type in critical_errors:
            return Severity.P0
        return Severity.P1


class CacheAlertStrategy(AlertStrategy):
    def evaluate(self, component_type: ComponentType, error_type: str) -> Severity:
        return Severity.P2


class DefaultAlertStrategy(AlertStrategy):
    def evaluate(self, component_type: ComponentType, error_type: str) -> Severity:
        return Severity.P3


def get_alert_strategy(component_type: ComponentType) -> AlertStrategy:
    if component_type == ComponentType.RDBMS:
        return RDBMSAlertStrategy()
    elif component_type == ComponentType.CACHE:
        return CacheAlertStrategy()
    return DefaultAlertStrategy()


# ============================================================================
# ALERT INGESTION: Create incident from new AlertPayload format
# ============================================================================

async def ingest_alert(alert: AlertPayload) -> Optional[Dict[str, Any]]:
    """
    Process a new-format alert:
    1. Classify it
    2. Check for existing open incident on same service (dedup)
    3. Create new incident or update existing
    4. Send email notification
    5. Log to audit trail

    Returns the incident dict if created/found, None on error.
    """
    from services.email import send_new_infrastructure_incident, send_new_application_incident

    classified = classify_alert(alert)
    pg_pool = get_pg()

    async with pg_pool.acquire() as conn:
        # Check if there's already an open incident for this service
        existing = await conn.fetchrow(
            """SELECT id, status, signal_count FROM work_items
               WHERE service = $1
                 AND status NOT IN ('RESOLVED', 'CLOSED')
               ORDER BY created_at DESC LIMIT 1""",
            alert.service
        )

        if existing:
            # Update existing incident — increment signal count
            await conn.execute(
                """UPDATE work_items
                   SET signal_count = signal_count + 1,
                       last_signal_at = NOW(),
                       updated_at = NOW()
                   WHERE id = $1""",
                existing["id"]
            )
            logger.info(
                f"Updated existing incident {existing['id']} for service {alert.service} "
                f"(signal_count now {existing['signal_count'] + 1})"
            )
            return {"id": str(existing["id"]), "action": "updated"}

        # Create new incident
        row = await conn.fetchrow(
            """INSERT INTO work_items (
                component_id, component_type, severity, status, title,
                incident_type, service, message_text, source,
                first_signal_at, last_signal_at
            ) VALUES ($1, $2, $3, 'DETECTED', $4, $5, $6, $7, $8, NOW(), NOW())
            RETURNING id, incident_type, severity, service, message_text,
                      component_id, title, created_at, escalation_count""",
            classified.component_id,
            classified.component_type,
            classified.normalized_severity,
            classified.title,
            classified.incident_type.value,
            alert.service,
            alert.message,
            alert.source,
        )

        incident = dict(row)
        incident["id"] = str(incident["id"])
        incident["created_at"] = incident["created_at"]

        # Log creation to audit
        await conn.execute(
            """INSERT INTO audit_log (incident_id, action, old_status, new_status, performed_by, notes)
               VALUES ($1, 'created', NULL, 'DETECTED', 'system', $2)""",
            row["id"],
            f"Incident created from {alert.source} alert"
        )

    logger.info(
        f"Created incident {incident['id']}: service={alert.service}, "
        f"type={classified.incident_type.value}, severity={classified.normalized_severity}"
    )

    # Send email notification (fire and forget)
    asyncio.create_task(_send_creation_email(incident))

    return {**incident, "action": "created"}


async def _send_creation_email(incident: dict):
    """Fire-and-forget email notification on incident creation."""
    from services.email import send_new_infrastructure_incident, send_new_application_incident

    try:
        pg_pool = get_pg()
        if incident.get("incident_type") == "infrastructure":
            to_email, subject, body, success = send_new_infrastructure_incident(incident)
        else:
            to_email, subject, body, success = send_new_application_incident(incident)

        # Log to notifications table
        import uuid as _uuid
        incident_uuid = _uuid.UUID(incident["id"])
        async with pg_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO notifications (incident_id, email_to, subject, body, type, status)
                   VALUES ($1, $2, $3, $4, 'email', $5)""",
                incident_uuid,
                to_email,
                subject,
                body,
                "sent" if success else "failed"
            )
    except Exception as e:
        logger.error(f"Failed to send creation email for incident {incident.get('id')}: {e}")


# ============================================================================
# LEGACY: Create work item from SignalPayload (original format)
# ============================================================================

async def process_new_work_item(signal: SignalPayload):
    """Create a new Work Item based on a legacy signal."""
    strategy = get_alert_strategy(signal.component_type)
    severity = strategy.evaluate(signal.component_type, signal.error_type)

    title = f"{signal.component_type.value} Alert: {signal.error_type} on {signal.component_id}"

    pg_pool = get_pg()
    query = """
        INSERT INTO work_items (component_id, component_type, severity, status, title,
                                incident_type, service, message_text, source,
                                first_signal_at, last_signal_at)
        VALUES ($1, $2, $3, 'DETECTED', $4, 'infrastructure', $5, $6, 'internal', $7, $8)
        RETURNING id
    """
    try:
        async with pg_pool.acquire() as conn:
            work_item_id = await conn.fetchval(
                query,
                signal.component_id,
                signal.component_type.value,
                severity.value,
                title,
                signal.component_id,
                signal.message,
                signal.timestamp,
                signal.timestamp
            )
            # Log creation
            await conn.execute(
                """INSERT INTO audit_log (incident_id, action, old_status, new_status, performed_by, notes)
                   VALUES ($1, 'created', NULL, 'DETECTED', 'system', $2)""",
                work_item_id,
                "Incident created from signal ingestion"
            )
            logger.info(f"Created Work Item: {title} with Severity {severity.value}")
    except Exception as e:
        logger.error(f"Failed to create Work Item: {e}")


# ============================================================================
# STATE MACHINE: Incident Lifecycle Enforcement
# ============================================================================

# Valid forward transitions only
VALID_TRANSITIONS = {
    IncidentStatus.DETECTED:      [IncidentStatus.ACKNOWLEDGED],
    IncidentStatus.ACKNOWLEDGED:  [IncidentStatus.INVESTIGATING],
    IncidentStatus.INVESTIGATING: [IncidentStatus.RESOLVED],
    IncidentStatus.RESOLVED:      [IncidentStatus.CLOSED],
    IncidentStatus.OPEN:          [IncidentStatus.ACKNOWLEDGED, IncidentStatus.INVESTIGATING],  # legacy
    IncidentStatus.CLOSED:        [],
}


class WorkItemState:
    """
    Manages incident lifecycle state machine.

    Valid transitions (forward only):
        DETECTED → ACKNOWLEDGED → INVESTIGATING → RESOLVED → CLOSED
    """

    async def transition(
        self,
        work_item_id: str,
        new_status: IncidentStatus,
        performed_by: str = "user",
        resolution_note: Optional[str] = None
    ) -> bool:
        from services.email import send_resolved_email

        # Fetch current status
        pg_pool = get_pg()
        async with pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT status, incident_type, severity, service, message_text,
                          component_id, title, created_at, escalation_count, resolution_note
                   FROM work_items WHERE id = $1""",
                work_item_id
            )

        if not row:
            raise ValueError(f"Incident {work_item_id} not found")

        current_status_str = row["status"]
        try:
            current_status = IncidentStatus(current_status_str)
        except ValueError:
            current_status = IncidentStatus.OPEN

        # Validate forward-only transition
        allowed = VALID_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {current_status.value} → {new_status.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        # Require resolution note when resolving
        if new_status == IncidentStatus.RESOLVED and not resolution_note:
            raise ValueError("resolution_note is required when resolving an incident")

        # Require RCA record when closing (legacy path)
        if new_status == IncidentStatus.CLOSED:
            async with pg_pool.acquire() as conn:
                rca = await conn.fetchval(
                    "SELECT id FROM rca_records WHERE work_item_id = $1",
                    work_item_id
                )
            # Allow close without RCA if resolution_note is set (new flow)
            if not rca:
                async with pg_pool.acquire() as conn:
                    res_note = await conn.fetchval(
                        "SELECT resolution_note FROM work_items WHERE id = $1",
                        work_item_id
                    )
                if not res_note:
                    raise ValueError("Cannot close incident: no resolution note or RCA found.")

        # Build update fields
        update_fields = ["status = $1", "updated_at = NOW()"]
        params = [new_status.value]
        idx = 2

        if new_status == IncidentStatus.ACKNOWLEDGED:
            update_fields.append(f"acknowledged_at = NOW()")
        elif new_status == IncidentStatus.RESOLVED:
            update_fields.append(f"resolved_at = NOW()")
            if resolution_note:
                update_fields.append(f"resolution_note = ${idx}")
                params.append(resolution_note)
                idx += 1
        elif new_status == IncidentStatus.CLOSED:
            update_fields.append(f"closed_at = NOW()")

        params.append(work_item_id)
        update_query = f"UPDATE work_items SET {', '.join(update_fields)} WHERE id = ${idx}"

        import uuid as _uuid
        incident_uuid = _uuid.UUID(work_item_id)

        async with pg_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(update_query, *params)

                # Audit log
                await conn.execute(
                    """INSERT INTO audit_log (incident_id, action, old_status, new_status, performed_by, notes)
                       VALUES ($1, 'state_change', $2, $3, $4, $5)""",
                    incident_uuid,
                    current_status_str,
                    new_status.value,
                    performed_by,
                    resolution_note or f"Transitioned to {new_status.value}"
                )

        logger.info(
            f"State transition: {work_item_id} → {new_status.value} "
            f"(by {performed_by})"
        )

        # Send resolved email async
        if new_status == IncidentStatus.RESOLVED:
            incident = dict(row)
            incident["id"] = work_item_id
            incident["resolved_at"] = datetime.now(timezone.utc)
            asyncio.create_task(_send_resolved_email_task(incident, resolution_note or ""))

        return True

    async def _validate_transition(self, work_item_id: str, new_status: IncidentStatus) -> bool:
        # kept for backward compat
        return True


async def _send_resolved_email_task(incident: dict, resolution_note: str):
    """Fire-and-forget resolved email."""
    from services.email import send_resolved_email
    try:
        pg_pool = get_pg()
        to_email, subject, body, success = send_resolved_email(incident, resolution_note)
        import uuid as _uuid
        incident_uuid = _uuid.UUID(incident["id"])
        async with pg_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO notifications (incident_id, email_to, subject, body, type, status)
                   VALUES ($1, $2, $3, $4, 'email', $5)""",
                incident_uuid,
                to_email,
                subject,
                body,
                "sent" if success else "failed"
            )
    except Exception as e:
        logger.error(f"Failed to send resolved email: {e}")


# ============================================================================
# RCA Submission (legacy flow — still supported)
# ============================================================================

async def submit_rca(work_item_id: str, rca: RCASubmission) -> Dict[str, Any]:
    """Submit RCA and transition to CLOSED."""

    if not rca.root_cause_detail or len(rca.root_cause_detail) < 10:
        raise ValueError("Root cause detail must be at least 10 characters.")
    if not rca.fix_applied or len(rca.fix_applied) < 10:
        raise ValueError("Fix applied must be at least 10 characters.")
    if not rca.prevention_steps or len(rca.prevention_steps) < 10:
        raise ValueError("Prevention steps must be at least 10 characters.")
    if rca.incident_end <= rca.incident_start:
        raise ValueError("incident_end must be after incident_start.")

    mttr_seconds = int((rca.incident_end - rca.incident_start).total_seconds())
    logger.info(f"MTTR Calculated: {mttr_seconds} seconds for {work_item_id}")

    import uuid as _uuid
    work_item_uuid = _uuid.UUID(work_item_id)

    pg_pool = get_pg()
    rca_insert_query = """
        INSERT INTO rca_records (
            work_item_id, incident_start, incident_end, root_cause_category,
            root_cause_detail, fix_applied, prevention_steps, mttr_seconds
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
    """

    async with pg_pool.acquire() as conn:
        async with conn.transaction():
            rca_id = await conn.fetchval(
                rca_insert_query,
                work_item_uuid,
                rca.incident_start,
                rca.incident_end,
                rca.root_cause_category.value,
                rca.root_cause_detail,
                rca.fix_applied,
                rca.prevention_steps,
                mttr_seconds
            )
            # Update to CLOSED directly (RCA implies resolution)
            await conn.execute(
                """UPDATE work_items
                   SET status = 'CLOSED', resolved_at = NOW(), closed_at = NOW(),
                       resolution_note = $1, updated_at = NOW()
                   WHERE id = $2""",
                rca.fix_applied,
                work_item_uuid
            )
            await conn.execute(
                """INSERT INTO audit_log (incident_id, action, old_status, new_status, performed_by, notes)
                   VALUES ($1, 'rca_submitted', 'RESOLVED', 'CLOSED', 'user', $2)""",
                work_item_uuid,
                f"RCA submitted, MTTR={mttr_seconds}s"
            )
            logger.info(f"RCA submitted: id={rca_id}, mttr={mttr_seconds}s")

    return {
        "rca_id": str(rca_id),
        "mttr_seconds": mttr_seconds,
        "status": "CLOSED"
    }