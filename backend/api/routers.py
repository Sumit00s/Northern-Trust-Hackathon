import time
import psutil
import uuid as _uuid
from fastapi import APIRouter, Request, HTTPException, Query, Body
from typing import List, Optional

from models.schemas import (
    SignalBatch, SignalPayload, WorkItemResponse,
    RCASubmission, RCAResponse, HealthResponse, DashboardState,
    IncidentStatus, AlertPayload, IncidentResponse,
    NotificationResponse, AuditLogResponse, ResolveRequest
)
from services.ingestion import check_rate_limit, ingest_signal
from services.workflow import submit_rca, WorkItemState, ingest_alert
from db.database import get_pg, get_mongo, get_redis
from config import settings

router = APIRouter()
start_time = time.time()


# ─── Health ──────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Observability /health endpoint"""
    redis_client = get_redis()
    pg_pool = get_pg()

    count_str = await redis_client.get("metric:signals_count")
    count = int(count_str) if count_str else 0
    signals_per_sec = count / 5.0

    pool_size = pg_pool.get_size()
    pool_free = pg_pool.get_idle_size()

    return HealthResponse(
        status="healthy",
        uptime_seconds=time.time() - start_time,
        signals_per_sec=signals_per_sec,
        queue_depth=0,
        pg_pool_size=pool_size,
        pg_pool_free=pool_free
    )


# ─── NEW: Alert Ingestion (simplified format from simulator) ─────────────────

@router.post("/alerts", status_code=202)
async def ingest_alert_endpoint(alert: AlertPayload):
    """
    Accept simplified alert from monitoring tool / simulator.
    Classifies, deduplicates, creates incident, sends email.
    """
    result = await ingest_alert(alert)
    return {"status": "accepted", "action": result.get("action"), "incident_id": result.get("id")}


# ─── LEGACY: Signal Ingestion ─────────────────────────────────────────────────

@router.post("/signals", status_code=202)
async def ingest_signals(request: Request, batch: SignalBatch):
    """High-throughput legacy ingestion API"""
    client_ip = request.client.host if request.client else "0.0.0.0"
    await check_rate_limit(client_ip, settings.rate_limit_per_second)

    for signal in batch.signals:
        await ingest_signal(signal)

    return {"status": "accepted", "count": len(batch.signals)}


# ─── NEW: Incidents API (primary API for the dashboard) ──────────────────────

def _row_to_incident(row) -> dict:
    """Convert a DB row to an incident response dict."""
    d = dict(row)
    d["id"] = str(d["id"])
    return d


@router.get("/incidents", response_model=List[IncidentResponse])
async def list_incidents(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    incident_type: Optional[str] = Query(None),
):
    """List all incidents ordered by severity then created_at."""
    pg_pool = get_pg()

    filters = []
    params = []
    idx = 1

    if status:
        filters.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if incident_type:
        filters.append(f"incident_type = ${idx}")
        params.append(incident_type)
        idx += 1

    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    params += [limit, offset]

    query = f"""
        SELECT id, component_id, component_type, severity, status, title,
               signal_count, first_signal_at, last_signal_at, assigned_to,
               created_at, updated_at, incident_type, service, message_text,
               source, acknowledged_at, resolved_at, closed_at,
               escalation_count, resolution_note
        FROM work_items
        {where}
        ORDER BY
            CASE severity
                WHEN 'P0' THEN 1
                WHEN 'P1' THEN 2
                WHEN 'P2' THEN 3
                WHEN 'P3' THEN 4
                WHEN 'P4' THEN 5
            END,
            CASE status
                WHEN 'DETECTED' THEN 1
                WHEN 'ACKNOWLEDGED' THEN 2
                WHEN 'INVESTIGATING' THEN 3
                WHEN 'RESOLVED' THEN 4
                WHEN 'CLOSED' THEN 5
                ELSE 6
            END,
            created_at DESC
        LIMIT ${idx} OFFSET ${idx+1}
    """

    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    return [IncidentResponse(**_row_to_incident(r)) for r in rows]


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    """Get full incident details including audit log and notifications."""
    pg_pool = get_pg()

    try:
        incident_uuid = _uuid.UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident ID format")

    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, component_id, component_type, severity, status, title,
                      signal_count, first_signal_at, last_signal_at, assigned_to,
                      created_at, updated_at, incident_type, service, message_text,
                      source, acknowledged_at, resolved_at, closed_at,
                      escalation_count, resolution_note
               FROM work_items WHERE id = $1""",
            incident_uuid
        )
        if not row:
            raise HTTPException(status_code=404, detail="Incident not found")

        audit_rows = await conn.fetch(
            """SELECT id, incident_id, action, old_status, new_status,
                      performed_by, timestamp, notes
               FROM audit_log WHERE incident_id = $1
               ORDER BY timestamp ASC""",
            incident_uuid
        )

        notif_rows = await conn.fetch(
            """SELECT id, incident_id, email_to, subject, body, sent_at, type, status
               FROM notifications WHERE incident_id = $1
               ORDER BY sent_at DESC""",
            incident_uuid
        )

    incident = _row_to_incident(row)
    audit_log = [
        {**dict(r), "id": str(r["id"]), "incident_id": str(r["incident_id"])}
        for r in audit_rows
    ]
    notifications = [
        {**dict(r), "id": str(r["id"]), "incident_id": str(r["incident_id"])}
        for r in notif_rows
    ]

    return {
        "incident": incident,
        "audit_log": audit_log,
        "notifications": notifications,
    }


# ─── Incident State Transitions ──────────────────────────────────────────────

@router.patch("/incidents/{incident_id}/acknowledge")
async def acknowledge_incident(incident_id: str):
    """Move incident to ACKNOWLEDGED state."""
    state_manager = WorkItemState()
    try:
        await state_manager.transition(incident_id, IncidentStatus.ACKNOWLEDGED, performed_by="user")
        return {"status": "success", "new_status": "ACKNOWLEDGED"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/incidents/{incident_id}/investigate")
async def investigate_incident(incident_id: str):
    """Move incident to INVESTIGATING state."""
    state_manager = WorkItemState()
    try:
        await state_manager.transition(incident_id, IncidentStatus.INVESTIGATING, performed_by="user")
        return {"status": "success", "new_status": "INVESTIGATING"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/incidents/{incident_id}/resolve")
async def resolve_incident(incident_id: str, body: ResolveRequest):
    """Move incident to RESOLVED state (requires resolution_note)."""
    state_manager = WorkItemState()
    try:
        await state_manager.transition(
            incident_id, IncidentStatus.RESOLVED,
            performed_by="user",
            resolution_note=body.resolution_note
        )
        return {"status": "success", "new_status": "RESOLVED"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/incidents/{incident_id}/close")
async def close_incident(incident_id: str):
    """Move incident to CLOSED state."""
    state_manager = WorkItemState()
    try:
        await state_manager.transition(incident_id, IncidentStatus.CLOSED, performed_by="user")
        return {"status": "success", "new_status": "CLOSED"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── LEGACY: Work Items API (kept for backward compatibility) ────────────────

@router.get("/work_items", response_model=List[WorkItemResponse])
async def get_work_items(limit: int = Query(50, le=500), offset: int = Query(0, ge=0)):
    """Legacy: Retrieve incidents as work items."""
    pg_pool = get_pg()
    query = """
        SELECT id, component_id, component_type, severity, status, title,
               signal_count, first_signal_at, last_signal_at, assigned_to,
               created_at, updated_at
        FROM work_items
        ORDER BY
            CASE severity
                WHEN 'P0' THEN 1
                WHEN 'P1' THEN 2
                WHEN 'P2' THEN 3
                WHEN 'P3' THEN 4
                WHEN 'P4' THEN 5
            END,
            created_at DESC
        LIMIT $1 OFFSET $2
    """
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(query, limit, offset)

    return [WorkItemResponse(**{**dict(r), "id": str(r["id"])}) for r in rows]


@router.get("/work_items/{item_id}/signals")
async def get_work_item_signals(item_id: str):
    """Retrieve raw signals linked to a component from MongoDB."""
    pg_pool = get_pg()
    try:
        item_uuid = _uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item ID")

    query = "SELECT component_id, first_signal_at FROM work_items WHERE id = $1"
    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow(query, item_uuid)

    if not row:
        raise HTTPException(status_code=404, detail="Work item not found")

    component_id = row["component_id"]
    mongo_db = get_mongo()
    cursor = mongo_db["signals"].find({"component_id": component_id}).sort("timestamp", -1).limit(100)
    signals = await cursor.to_list(length=100)

    for sig in signals:
        sig["_id"] = str(sig["_id"])

    return signals


@router.post("/work_items/{item_id}/status")
async def update_status(item_id: str, target_status: IncidentStatus):
    """Legacy: transition work item status."""
    state_manager = WorkItemState()
    try:
        success = await state_manager.transition(item_id, target_status)
        if success:
            return {"status": "success", "new_status": target_status}
        raise HTTPException(status_code=400, detail="Transition failed")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/work_items/{item_id}/rca")
async def create_rca(item_id: str, rca: RCASubmission):
    """Submit RCA and transition to CLOSED."""
    try:
        result = await submit_rca(item_id, rca)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Analytics ────────────────────────────────────────────────────────────────

@router.get("/analytics")
async def get_analytics():
    """Get incident analytics: MTTR, frequency by service, counts."""
    pg_pool = get_pg()
    async with pg_pool.acquire() as conn:
        # Total counts by status
        counts = await conn.fetch(
            """SELECT status, COUNT(*) as count FROM work_items GROUP BY status"""
        )

        # Resolved today
        resolved_today = await conn.fetchval(
            """SELECT COUNT(*) FROM work_items
               WHERE status IN ('RESOLVED', 'CLOSED')
               AND resolved_at >= NOW() - INTERVAL '24 hours'"""
        )

        # Average MTTR
        avg_mttr = await conn.fetchval(
            """SELECT AVG(mttr_seconds) FROM rca_records"""
        )

        # Incidents by service (top 10)
        by_service = await conn.fetch(
            """SELECT service, COUNT(*) as count, MAX(severity) as max_severity
               FROM work_items
               WHERE service IS NOT NULL
               GROUP BY service
               ORDER BY count DESC
               LIMIT 10"""
        )

        # Incidents by type
        by_type = await conn.fetch(
            """SELECT incident_type, COUNT(*) as count
               FROM work_items GROUP BY incident_type"""
        )

    return {
        "counts_by_status": {r["status"]: r["count"] for r in counts},
        "resolved_today": resolved_today or 0,
        "avg_mttr_seconds": float(avg_mttr) if avg_mttr else 0.0,
        "incidents_by_service": [dict(r) for r in by_service],
        "incidents_by_type": {r["incident_type"]: r["count"] for r in by_type},
    }
