-- ═══════════════════════════════════════════════════════════════════
-- IMS PostgreSQL Schema — Source of Truth
-- TimescaleDB extension for time-series aggregations
-- ═══════════════════════════════════════════════════════════════════

-- Enable TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ─── Work Items (Incident Records) ──────────────────────────────
CREATE TABLE IF NOT EXISTS work_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Original fields (kept for compatibility)
    component_id    VARCHAR(100) NOT NULL,
    component_type  VARCHAR(50)  NOT NULL,
    severity        VARCHAR(5)   NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'DETECTED',
    title           TEXT         NOT NULL,
    signal_count    INTEGER      NOT NULL DEFAULT 1,
    first_signal_at TIMESTAMPTZ  NOT NULL,
    last_signal_at  TIMESTAMPTZ  NOT NULL,
    assigned_to     VARCHAR(100),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- New fields for DevOps incident management
    incident_type   VARCHAR(20)  NOT NULL DEFAULT 'infrastructure',  -- infrastructure | application
    service         VARCHAR(100),       -- e.g. web-server-01, checkout-api
    message_text    TEXT,               -- Human-readable alert message
    source          VARCHAR(50),        -- prometheus, datadog, etc.
    acknowledged_at TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    closed_at       TIMESTAMPTZ,
    escalation_count INTEGER     NOT NULL DEFAULT 0,
    resolution_note TEXT,

    CONSTRAINT chk_status CHECK (status IN ('DETECTED', 'ACKNOWLEDGED', 'INVESTIGATING', 'RESOLVED', 'CLOSED', 'OPEN')),
    CONSTRAINT chk_severity CHECK (severity IN ('P0', 'P1', 'P2', 'P3', 'P4')),
    CONSTRAINT chk_incident_type CHECK (incident_type IN ('infrastructure', 'application'))
);

CREATE INDEX IF NOT EXISTS idx_work_items_status ON work_items(status);
CREATE INDEX IF NOT EXISTS idx_work_items_severity ON work_items(severity);
CREATE INDEX IF NOT EXISTS idx_work_items_component ON work_items(component_id);
CREATE INDEX IF NOT EXISTS idx_work_items_incident_type ON work_items(incident_type);
CREATE INDEX IF NOT EXISTS idx_work_items_service ON work_items(service);
CREATE INDEX IF NOT EXISTS idx_work_items_created_at ON work_items(created_at DESC);

-- ─── Notifications Log ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notifications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID        NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    email_to    VARCHAR(255) NOT NULL,
    subject     TEXT         NOT NULL,
    body        TEXT         NOT NULL,
    sent_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    type        VARCHAR(50)  NOT NULL DEFAULT 'email',   -- email, sms, slack
    status      VARCHAR(20)  NOT NULL DEFAULT 'sent'     -- sent, failed
);

CREATE INDEX IF NOT EXISTS idx_notifications_incident ON notifications(incident_id);
CREATE INDEX IF NOT EXISTS idx_notifications_sent_at ON notifications(sent_at DESC);

-- ─── Audit Log ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id  UUID        NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    action       VARCHAR(50)  NOT NULL,   -- state_change, escalation, comment
    old_status   VARCHAR(20),
    new_status   VARCHAR(20),
    performed_by VARCHAR(100) NOT NULL DEFAULT 'system',
    timestamp    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    notes        TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_log_incident ON audit_log(incident_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);

-- ─── RCA Records (Root Cause Analysis) ──────────────────────────
CREATE TABLE IF NOT EXISTS rca_records (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id        UUID UNIQUE NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    incident_start      TIMESTAMPTZ NOT NULL,
    incident_end        TIMESTAMPTZ NOT NULL,
    root_cause_category VARCHAR(50) NOT NULL,
    root_cause_detail   TEXT        NOT NULL,
    fix_applied         TEXT        NOT NULL,
    prevention_steps    TEXT        NOT NULL,
    mttr_seconds        INTEGER     NOT NULL DEFAULT 0,
    submitted_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_rca_category CHECK (root_cause_category IN (
        'Infrastructure', 'Code Bug', 'Configuration',
        'External Dependency', 'Capacity', 'Network', 'Unknown'
    ))
);

-- ─── Signal Metrics (TimescaleDB Hypertable) ────────────────────
CREATE TABLE IF NOT EXISTS signal_metrics (
    time            TIMESTAMPTZ  NOT NULL,
    component_id    VARCHAR(100) NOT NULL,
    component_type  VARCHAR(50)  NOT NULL,
    signal_count    INTEGER      NOT NULL DEFAULT 1,
    avg_latency_ms  DOUBLE PRECISION
);

SELECT create_hypertable('signal_metrics', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_signal_metrics_component ON signal_metrics(component_id, time DESC);