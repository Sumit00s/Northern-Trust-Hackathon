"""
Email Notification Service
Uses Python's built-in smtplib with Gmail SMTP.
Sends HTML emails for incident lifecycle events.
"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from config import settings

logger = logging.getLogger("ims.email")


def _build_html_email(title: str, content_rows: list[tuple[str, str]], footer: str = "") -> str:
    """Build a professional HTML email body."""
    rows_html = ""
    for label, value in content_rows:
        rows_html += f"""
        <tr>
            <td style="padding: 8px 16px; font-weight: bold; color: #6b7280; width: 160px; vertical-align: top;">{label}</td>
            <td style="padding: 8px 16px; color: #1f2937;">{value}</td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background:#f3f4f6;">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding: 32px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
        
        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#1e3a5f,#2563eb);padding:28px 32px;">
            <div style="display:flex;align-items:center;">
              <span style="font-size:22px;font-weight:700;color:#ffffff;letter-spacing:-0.5px;">🛡️ IMS</span>
              <span style="color:#93c5fd;font-size:14px;margin-left:12px;">Incident Management System</span>
            </div>
          </td>
        </tr>

        <!-- Title -->
        <tr>
          <td style="padding:24px 32px 8px;">
            <h2 style="margin:0;font-size:20px;color:#111827;">{title}</h2>
          </td>
        </tr>

        <!-- Details -->
        <tr>
          <td style="padding:8px 16px 16px;">
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;border-radius:8px;border:1px solid #e5e7eb;">
              {rows_html}
            </table>
          </td>
        </tr>

        <!-- Footer -->
        {'<tr><td style="padding:16px 32px;color:#6b7280;font-size:13px;">' + footer + '</td></tr>' if footer else ''}

        <!-- Bottom bar -->
        <tr>
          <td style="background:#f9fafb;padding:16px 32px;border-top:1px solid #e5e7eb;">
            <p style="margin:0;color:#9ca3af;font-size:12px;">
              This is an automated notification from the Incident Management System.<br>
              Sent at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """
    Send an HTML email via Gmail SMTP.
    Returns True if sent successfully, False otherwise.
    """
    if not settings.smtp_password or settings.smtp_password in ("your-app-password", ""):
        logger.warning(f"SMTP not configured — skipping email to {to_email}: {subject}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_user
        msg["To"] = to_email

        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, to_email, msg.as_string())

        logger.info(f"Email sent to {to_email}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_new_infrastructure_incident(incident: dict) -> tuple[str, str, str, bool]:
    """
    Notify on-call engineer of a new infrastructure incident.
    Returns (to_email, subject, body, success).
    """
    severity = incident.get("severity", "P1")
    service = incident.get("service", incident.get("component_id", "unknown"))
    message = incident.get("message_text", incident.get("title", ""))
    incident_id = incident.get("id", "")
    created_at = incident.get("created_at", datetime.utcnow())
    if isinstance(created_at, datetime):
        created_at = created_at.strftime("%Y-%m-%d %H:%M:%S UTC")

    to_email = settings.oncall_email
    subject = f"[{severity} CRITICAL] Infrastructure Incident — {service}"

    title_color = "#dc2626" if severity in ("P1", "P0") else "#ea580c"
    body = _build_html_email(
        title=f"🚨 Infrastructure Incident Detected",
        content_rows=[
            ("Severity", f'<span style="background:{title_color};color:#fff;padding:2px 10px;border-radius:20px;font-weight:bold;">{severity} CRITICAL</span>'),
            ("Service", f"<strong>{service}</strong>"),
            ("Type", "Infrastructure"),
            ("Description", message),
            ("Incident ID", f'<code style="background:#f3f4f6;padding:2px 8px;border-radius:4px;">{incident_id}</code>'),
            ("Detected At", created_at),
        ],
        footer=f'🔴 <strong>Action Required:</strong> Please acknowledge this incident immediately. '
               f'Visit the <a href="http://localhost:3001" style="color:#2563eb;">IMS Dashboard</a> to take action.'
    )

    success = send_email(to_email, subject, body)
    return to_email, subject, body, success


def send_new_application_incident(incident: dict) -> tuple[str, str, str, bool]:
    """
    Notify app support team of a new application incident.
    Returns (to_email, subject, body, success).
    """
    severity = incident.get("severity", "P3")
    service = incident.get("service", incident.get("component_id", "unknown"))
    message = incident.get("message_text", incident.get("title", ""))
    incident_id = incident.get("id", "")
    created_at = incident.get("created_at", datetime.utcnow())
    if isinstance(created_at, datetime):
        created_at = created_at.strftime("%Y-%m-%d %H:%M:%S UTC")

    to_email = settings.app_team_email
    subject = f"[{severity} WARNING] Application Incident — {service}"

    body = _build_html_email(
        title=f"⚠️ Application Incident Detected",
        content_rows=[
            ("Severity", f'<span style="background:#d97706;color:#fff;padding:2px 10px;border-radius:20px;font-weight:bold;">{severity} WARNING</span>'),
            ("Service", f"<strong>{service}</strong>"),
            ("Type", "Application"),
            ("Description", message),
            ("Incident ID", f'<code style="background:#f3f4f6;padding:2px 8px;border-radius:4px;">{incident_id}</code>'),
            ("Detected At", created_at),
        ],
        footer=f'ℹ️ This is a non-critical application incident. '
               f'Visit the <a href="http://localhost:3001" style="color:#2563eb;">IMS Dashboard</a> to track progress.'
    )

    success = send_email(to_email, subject, body)
    return to_email, subject, body, success


def send_escalation_email(incident: dict, minutes_open: int) -> tuple[str, str, str, bool]:
    """
    Send escalation email to senior engineer when incident is unacknowledged.
    Returns (to_email, subject, body, success).
    """
    severity = incident.get("severity", "P1")
    service = incident.get("service", incident.get("component_id", "unknown"))
    message = incident.get("message_text", incident.get("title", ""))
    incident_id = incident.get("id", "")

    to_email = settings.senior_email
    subject = f"[ESCALATED] 🔴 Infrastructure incident NOT acknowledged — {service}"

    body = _build_html_email(
        title=f"🚨 ESCALATION: Incident Not Acknowledged",
        content_rows=[
            ("Severity", f'<span style="background:#dc2626;color:#fff;padding:2px 10px;border-radius:20px;font-weight:bold;">{severity} — ESCALATED</span>'),
            ("Service", f"<strong>{service}</strong>"),
            ("Time Open", f'<span style="color:#dc2626;font-weight:bold;">{minutes_open} minutes</span> without acknowledgement'),
            ("Description", message),
            ("Incident ID", f'<code style="background:#f3f4f6;padding:2px 8px;border-radius:4px;">{incident_id}</code>'),
        ],
        footer=f'🔴 <strong>URGENT:</strong> This incident has not been acknowledged for {minutes_open} minutes. '
               f'Senior engineer intervention required. <a href="http://localhost:3001" style="color:#2563eb;">Open Dashboard</a>'
    )

    success = send_email(to_email, subject, body)
    return to_email, subject, body, success


def send_reminder_email(incident: dict, minutes_open: int) -> tuple[str, str, str, bool]:
    """
    Send reminder email when an incident has been investigating for too long.
    Returns (to_email, subject, body, success).
    """
    severity = incident.get("severity", "P2")
    service = incident.get("service", incident.get("component_id", "unknown"))
    message = incident.get("message_text", incident.get("title", ""))
    incident_id = incident.get("id", "")
    incident_type = incident.get("incident_type", "infrastructure")

    to_email = settings.oncall_email if incident_type == "infrastructure" else settings.app_team_email
    subject = f"[REMINDER] Incident still open — {service}"

    body = _build_html_email(
        title=f"⏰ Reminder: Incident Still Under Investigation",
        content_rows=[
            ("Severity", f'<span style="background:#2563eb;color:#fff;padding:2px 10px;border-radius:20px;font-weight:bold;">{severity}</span>'),
            ("Service", f"<strong>{service}</strong>"),
            ("Time Investigating", f'<span style="color:#d97706;font-weight:bold;">{minutes_open} minutes</span>'),
            ("Description", message),
            ("Incident ID", f'<code style="background:#f3f4f6;padding:2px 8px;border-radius:4px;">{incident_id}</code>'),
        ],
        footer=f'ℹ️ This incident has been in INVESTIGATING state for {minutes_open} minutes. '
               f'Please update status or escalate. <a href="http://localhost:3001" style="color:#2563eb;">Open Dashboard</a>'
    )

    success = send_email(to_email, subject, body)
    return to_email, subject, body, success


def send_resolved_email(incident: dict, resolution_note: str) -> tuple[str, str, str, bool]:
    """
    Notify that an incident has been resolved.
    Returns (to_email, subject, body, success).
    """
    severity = incident.get("severity", "P2")
    service = incident.get("service", incident.get("component_id", "unknown"))
    incident_id = incident.get("id", "")
    incident_type = incident.get("incident_type", "infrastructure")

    # Calculate time to resolve
    created_at = incident.get("created_at")
    resolved_at = incident.get("resolved_at", datetime.utcnow())
    time_str = "N/A"
    if created_at and resolved_at:
        if isinstance(created_at, str):
            from datetime import datetime as dt
            try:
                created_at = dt.fromisoformat(created_at.replace("Z", "+00:00"))
            except Exception:
                pass
        if isinstance(created_at, datetime) and isinstance(resolved_at, datetime):
            delta = resolved_at - created_at.replace(tzinfo=None) if created_at.tzinfo else resolved_at - created_at
            minutes = int(abs(delta.total_seconds()) / 60)
            time_str = f"{minutes} minutes"

    to_email = settings.oncall_email if incident_type == "infrastructure" else settings.app_team_email
    subject = f"[RESOLVED] ✅ Incident closed — {service}"

    body = _build_html_email(
        title=f"✅ Incident Resolved",
        content_rows=[
            ("Severity", f'<span style="background:#16a34a;color:#fff;padding:2px 10px;border-radius:20px;font-weight:bold;">{severity} — RESOLVED</span>'),
            ("Service", f"<strong>{service}</strong>"),
            ("Total Time", f'<span style="color:#16a34a;font-weight:bold;">{time_str}</span>'),
            ("Resolution", resolution_note),
            ("Incident ID", f'<code style="background:#f3f4f6;padding:2px 8px;border-radius:4px;">{incident_id}</code>'),
        ],
        footer=f'✅ This incident has been successfully resolved. No further action required.'
    )

    success = send_email(to_email, subject, body)
    return to_email, subject, body, success
