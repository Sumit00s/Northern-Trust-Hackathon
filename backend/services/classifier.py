"""
Alert Classifier Service
Classifies incoming alerts by type and severity,
determines routing (who to notify), and prevents duplicate incidents.
"""

import logging
from typing import Optional

from models.schemas import AlertPayload, IncidentType, Severity

logger = logging.getLogger("ims.classifier")

# Severity mapping: infrastructure vs application
INFRA_SEVERITY_MAP = {
    "P1": "P1",  # Critical
    "P2": "P2",  # High
    "P3": "P2",  # Treat infra P3 as P2
    "P4": "P3",  # Treat infra P4 as P3
}

APP_SEVERITY_MAP = {
    "P1": "P2",  # App P1 max at P2
    "P2": "P3",
    "P3": "P3",
    "P4": "P4",
}


class ClassifiedAlert:
    """Result of alert classification."""
    def __init__(
        self,
        alert: AlertPayload,
        incident_type: IncidentType,
        normalized_severity: str,
        component_id: str,
        component_type: str,
        title: str,
    ):
        self.alert = alert
        self.incident_type = incident_type
        self.normalized_severity = normalized_severity
        self.component_id = component_id
        self.component_type = component_type
        self.title = title


def classify_alert(alert: AlertPayload) -> ClassifiedAlert:
    """
    Classify an incoming alert and determine its properties.
    
    Rules:
    - infrastructure → high priority, page on-call immediately
    - application → lower priority, notify app team
    - Severity normalization ensures infra is always higher priority
    """
    incident_type = IncidentType.INFRASTRUCTURE if alert.type == "infrastructure" else IncidentType.APPLICATION

    # Normalize severity based on type
    if incident_type == IncidentType.INFRASTRUCTURE:
        normalized_severity = INFRA_SEVERITY_MAP.get(alert.severity, "P2")
        component_type = _infer_infra_component_type(alert.service, alert.message)
        title = f"[{normalized_severity} INFRA] {alert.service} — {alert.message[:80]}"
    else:
        normalized_severity = APP_SEVERITY_MAP.get(alert.severity, "P3")
        component_type = "API"
        title = f"[{normalized_severity} APP] {alert.service} — {alert.message[:80]}"

    # Component ID is the service name (for dedup)
    component_id = alert.service.upper().replace("-", "_").replace(" ", "_")

    logger.info(
        f"Classified alert: service={alert.service}, "
        f"type={incident_type.value}, severity={normalized_severity}"
    )

    return ClassifiedAlert(
        alert=alert,
        incident_type=incident_type,
        normalized_severity=normalized_severity,
        component_id=component_id,
        component_type=component_type,
        title=title,
    )


def _infer_infra_component_type(service: str, message: str) -> str:
    """Infer component type from service name and message."""
    service_lower = service.lower()
    message_lower = message.lower()

    if any(k in service_lower or k in message_lower for k in ["db", "database", "postgres", "mysql", "mongo"]):
        return "RDBMS"
    elif any(k in service_lower or k in message_lower for k in ["redis", "cache", "memcache"]):
        return "CACHE"
    elif any(k in service_lower or k in message_lower for k in ["network", "packet", "switch", "router", "dns"]):
        return "NETWORK"
    elif any(k in service_lower or k in message_lower for k in ["server", "cpu", "memory", "disk", "host"]):
        return "SERVER"
    elif any(k in service_lower or k in message_lower for k in ["queue", "kafka", "rabbit", "mq"]):
        return "QUEUE"
    else:
        return "SERVER"