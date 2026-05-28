import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL
    ? `${import.meta.env.VITE_API_URL}/api`
    : 'http://localhost:8000/api';

export const api = axios.create({
    baseURL: API_URL,
});

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Incident {
    id: string;
    incident_type: 'infrastructure' | 'application';
    severity: 'P0' | 'P1' | 'P2' | 'P3' | 'P4';
    status: 'DETECTED' | 'ACKNOWLEDGED' | 'INVESTIGATING' | 'RESOLVED' | 'CLOSED' | 'OPEN';
    service: string | null;
    message_text: string | null;
    source: string | null;
    title: string;
    signal_count: number;
    assigned_to: string | null;
    escalation_count: number;
    resolution_note: string | null;
    created_at: string;
    updated_at: string;
    acknowledged_at: string | null;
    resolved_at: string | null;
    closed_at: string | null;
    // Legacy fields
    component_id: string;
    component_type: string;
    first_signal_at: string;
    last_signal_at: string;
}

export interface AuditEntry {
    id: string;
    incident_id: string;
    action: string;
    old_status: string | null;
    new_status: string | null;
    performed_by: string;
    timestamp: string;
    notes: string | null;
}

export interface Notification {
    id: string;
    incident_id: string;
    email_to: string;
    subject: string;
    body: string;
    sent_at: string;
    type: string;
    status: string;
}

export interface IncidentDetail {
    incident: Incident;
    audit_log: AuditEntry[];
    notifications: Notification[];
}

export interface Analytics {
    counts_by_status: Record<string, number>;
    resolved_today: number;
    avg_mttr_seconds: number;
    incidents_by_service: Array<{ service: string; count: number; max_severity: string }>;
    incidents_by_type: Record<string, number>;
}

export interface Health {
    status: string;
    uptime_seconds: number;
    signals_per_sec: number;
    pg_pool_size: number;
    pg_pool_free: number;
}

// Legacy WorkItem kept for compatibility
export interface WorkItem extends Incident { }
export interface Signal {
    _id: string;
    signal_id: string;
    component_id: string;
    component_type: string;
    error_type: string;
    message: string;
    payload: Record<string, unknown>;
    timestamp: string;
    latency_ms: number;
}

// ─── API Functions ────────────────────────────────────────────────────────────

export const fetchIncidents = async (): Promise<Incident[]> => {
    const { data } = await api.get('/incidents');
    return data;
};

export const fetchIncidentDetail = async (id: string): Promise<IncidentDetail> => {
    const { data } = await api.get(`/incidents/${id}`);
    return data;
};

export const acknowledgeIncident = async (id: string) => {
    const { data } = await api.patch(`/incidents/${id}/acknowledge`);
    return data;
};

export const investigateIncident = async (id: string) => {
    const { data } = await api.patch(`/incidents/${id}/investigate`);
    return data;
};

export const resolveIncident = async (id: string, resolution_note: string) => {
    const { data } = await api.patch(`/incidents/${id}/resolve`, { resolution_note });
    return data;
};

export const closeIncident = async (id: string) => {
    const { data } = await api.patch(`/incidents/${id}/close`);
    return data;
};

export const fetchAnalytics = async (): Promise<Analytics> => {
    const { data } = await api.get('/analytics');
    return data;
};

export const fetchHealth = async (): Promise<Health> => {
    const { data } = await api.get('/health');
    return data;
};

// Legacy
export const fetchWorkItems = async (): Promise<WorkItem[]> => fetchIncidents();
export const fetchSignals = async (itemId: string): Promise<Signal[]> => {
    const { data } = await api.get(`/work_items/${itemId}/signals`);
    return data;
};
export const submitRca = async (itemId: string, rca: unknown) => {
    const { data } = await api.post(`/work_items/${itemId}/rca`, rca);
    return data;
};