"""
Escalation Service — Background Job
Runs every 60 seconds to:
1. Escalate unacknowledged infrastructure incidents older than N minutes
2. Send reminders for incidents investigating for too long
3. Log all escalation actions to the audit_log table
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from config import settings
from db.database import get_pg
from services.email import send_escalation_email, send_reminder_email

logger = logging.getLogger("ims.escalation")


async def run_escalation_loop():
    """
    Main escalation loop — runs forever until cancelled.
    Checks every 60 seconds.
    """
    logger.info("Escalation loop started")
    while True:
        try:
            await asyncio.sleep(60)
            await check_escalations()
        except asyncio.CancelledError:
            logger.info("Escalation loop cancelled")
            break
        except Exception as e:
            logger.error(f"Escalation loop error: {e}", exc_info=True)


async def check_escalations():
    """Run all escalation checks."""
    logger.info("Running escalation checks...")
    await escalate_unacknowledged_incidents()
    await remind_long_investigating_incidents()


async def escalate_unacknowledged_incidents():
    """
    Find infrastructure incidents in DETECTED state with no acknowledgement
    for longer than escalation_timeout_minutes → escalate.
    """
    pg_pool = get_pg()
    threshold = datetime.now(timezone.utc) - timedelta(minutes=settings.escalation_timeout_minutes)

    query = """
        SELECT id, incident_type, severity, service, message_text, component_id, 
               title, created_at, escalation_count
        FROM work_items
        WHERE status = 'DETECTED'
          AND incident_type = 'infrastructure'
          AND created_at < $1
        ORDER BY severity ASC, created_at ASC
    """

    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(query, threshold)

    if not rows:
        return

    logger.warning(f"Found {len(rows)} unacknowledged infrastructure incidents to escalate")

    for row in rows:
        incident = dict(row)
        incident_id = str(incident["id"])
        created_at = incident["created_at"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        minutes_open = int((datetime.now(timezone.utc) - created_at).total_seconds() / 60)

        logger.warning(
            f"Escalating incident {incident_id} ({incident.get('service')}) "
            f"— open {minutes_open} minutes without acknowledgement"
        )

        # Send escalation email
        to_email, subject, body, success = send_escalation_email(incident, minutes_open)

        async with pg_pool.acquire() as conn:
            async with conn.transaction():
                # Increment escalation count
                await conn.execute(
                    "UPDATE work_items SET escalation_count = escalation_count + 1, updated_at = NOW() WHERE id = $1",
                    incident["id"]
                )

                # Log to audit
                await conn.execute(
                    """INSERT INTO audit_log (incident_id, action, old_status, new_status, performed_by, notes)
                       VALUES ($1, 'escalation', 'DETECTED', 'DETECTED', 'system', $2)""",
                    incident["id"],
                    f"Auto-escalated after {minutes_open} minutes without acknowledgement"
                )

                # Log notification
                if to_email:
                    await conn.execute(
                        """INSERT INTO notifications (incident_id, email_to, subject, body, type, status)
                           VALUES ($1, $2, $3, $4, 'email', $5)""",
                        incident["id"],
                        to_email,
                        subject,
                        body,
                        "sent" if success else "failed"
                    )


async def remind_long_investigating_incidents():
    """
    Find incidents in INVESTIGATING state for longer than reminder_timeout_minutes.
    Send a reminder email.
    """
    pg_pool = get_pg()
    threshold = datetime.now(timezone.utc) - timedelta(minutes=settings.reminder_timeout_minutes)

    query = """
        SELECT id, incident_type, severity, service, message_text, component_id,
               title, created_at
        FROM work_items
        WHERE status = 'INVESTIGATING'
          AND updated_at < $1
        ORDER BY severity ASC, created_at ASC
    """

    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(query, threshold)

    if not rows:
        return

    logger.info(f"Sending reminders for {len(rows)} long-investigating incidents")

    for row in rows:
        incident = dict(row)
        incident_id = str(incident["id"])
        created_at = incident["created_at"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        minutes_open = int((datetime.now(timezone.utc) - created_at).total_seconds() / 60)

        logger.info(f"Sending reminder for incident {incident_id} — investigating {minutes_open} minutes")

        to_email, subject, body, success = send_reminder_email(incident, minutes_open)

        async with pg_pool.acquire() as conn:
            async with conn.transaction():
                # Log to audit
                await conn.execute(
                    """INSERT INTO audit_log (incident_id, action, old_status, new_status, performed_by, notes)
                       VALUES ($1, 'reminder', 'INVESTIGATING', 'INVESTIGATING', 'system', $2)""",
                    incident["id"],
                    f"Reminder sent — incident investigating for {minutes_open} minutes"
                )

                # Log notification
                if to_email:
                    await conn.execute(
                        """INSERT INTO notifications (incident_id, email_to, subject, body, type, status)
                           VALUES ($1, $2, $3, $4, 'email', $5)""",
                        incident["id"],
                        to_email,
                        subject,
                        body,
                        "sent" if success else "failed"
                    )