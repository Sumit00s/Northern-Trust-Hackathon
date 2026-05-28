import React, { useEffect, useState, useCallback } from 'react';
import {
  ArrowLeft, Server, Code2, AlertOctagon, Clock, Mail,
  CheckCircle, Activity, FileText, RefreshCw, Terminal,
  ChevronRight, TriangleAlert, Zap
} from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';
import {
  fetchIncidentDetail, acknowledgeIncident, investigateIncident,
  closeIncident, type IncidentDetail, type AuditEntry, type Notification
} from '../api';
import { getSeverityBg, getStatusStyle, getSeverityRowBg } from './Dashboard';
import { ResolveModal } from './ResolveModal';

interface IncidentDetailProps {
  incidentId: string;
  onBack: () => void;
}

export const IncidentDetail: React.FC<IncidentDetailProps> = ({ incidentId, onBack }) => {
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showResolve, setShowResolve] = useState(false);

  const loadDetail = useCallback(async () => {
    try {
      const d = await fetchIncidentDetail(incidentId);
      setDetail(d);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    loadDetail();
    const interval = setInterval(loadDetail, 5000);
    return () => clearInterval(interval);
  }, [loadDetail]);

  const handleAction = async (action: 'acknowledge' | 'investigate' | 'close') => {
    if (!detail) return;
    setActionLoading(action);
    try {
      if (action === 'acknowledge') await acknowledgeIncident(incidentId);
      else if (action === 'investigate') await investigateIncident(incidentId);
      else if (action === 'close') await closeIncident(incidentId);
      await loadDetail();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Action failed';
      alert(msg);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Activity className="w-8 h-8 animate-spin text-blue-400" />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="text-center py-24 text-gray-500">
        <AlertOctagon className="w-12 h-12 mx-auto mb-3 opacity-30" />
        <p>Incident not found</p>
      </div>
    );
  }

  const { incident, audit_log, notifications } = detail;
  const statusStyle = getStatusStyle(incident.status);
  const isInfra = incident.incident_type === 'infrastructure';

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-right-8 duration-400">

      {/* Back + Action bar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </button>

        <div className="flex items-center gap-2">
          {incident.status === 'DETECTED' && (
            <button
              onClick={() => handleAction('acknowledge')}
              disabled={actionLoading === 'acknowledge'}
              className="px-4 py-2 bg-orange-500/15 text-orange-400 border border-orange-500/40 hover:bg-orange-500/30 rounded-lg text-sm font-semibold transition-all disabled:opacity-50"
            >
              {actionLoading === 'acknowledge' ? '...' : '✋ Acknowledge'}
            </button>
          )}
          {incident.status === 'ACKNOWLEDGED' && (
            <button
              onClick={() => handleAction('investigate')}
              disabled={actionLoading === 'investigate'}
              className="px-4 py-2 bg-blue-500/15 text-blue-400 border border-blue-500/40 hover:bg-blue-500/30 rounded-lg text-sm font-semibold transition-all disabled:opacity-50"
            >
              {actionLoading === 'investigate' ? '...' : '🔍 Start Investigating'}
            </button>
          )}
          {incident.status === 'INVESTIGATING' && (
            <button
              onClick={() => setShowResolve(true)}
              className="px-4 py-2 bg-green-500/15 text-green-400 border border-green-500/40 hover:bg-green-500/30 rounded-lg text-sm font-semibold transition-all"
            >
              ✅ Mark Resolved
            </button>
          )}
          {incident.status === 'RESOLVED' && (
            <button
              onClick={() => handleAction('close')}
              disabled={actionLoading === 'close'}
              className="px-4 py-2 bg-gray-500/15 text-gray-400 border border-gray-500/40 hover:bg-gray-500/30 rounded-lg text-sm font-semibold transition-all disabled:opacity-50"
            >
              {actionLoading === 'close' ? '...' : '🔒 Close Incident'}
            </button>
          )}
          <button onClick={loadDetail} className="p-2 text-gray-400 hover:text-white transition-colors">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main incident card */}
      <div className={clsx('glass-panel rounded-2xl p-6 relative overflow-hidden border-l-4', getSeverityRowBg(incident.severity).replace('border-l-4 ', ''))}>
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2 flex-wrap">
              <span className={clsx('px-2.5 py-1 rounded-lg text-sm font-bold border', getSeverityBg(incident.severity))}>
                {incident.severity}
              </span>
              <span className={clsx(
                'px-2.5 py-1 rounded-lg text-xs font-semibold border flex items-center gap-1.5',
                isInfra
                  ? 'bg-red-500/15 text-red-400 border-red-500/30'
                  : 'bg-blue-500/15 text-blue-400 border-blue-500/30'
              )}>
                {isInfra ? <Server className="w-3 h-3" /> : <Code2 className="w-3 h-3" />}
                {isInfra ? 'Infrastructure' : 'Application'}
              </span>
              <span className={clsx('px-2.5 py-1 rounded-full text-xs font-medium border flex items-center gap-1.5', statusStyle.bg)}>
                <div className={clsx('w-1.5 h-1.5 rounded-full', statusStyle.dot)} />
                {incident.status}
              </span>
              {incident.escalation_count > 0 && (
                <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-red-500/15 text-red-400 border border-red-500/30 flex items-center gap-1">
                  <Zap className="w-3 h-3" /> Escalated ×{incident.escalation_count}
                </span>
              )}
            </div>
            <h1 className="text-xl font-bold text-white mb-2">
              {incident.service || incident.component_id}
            </h1>
            <p className="text-gray-400 text-sm leading-relaxed">
              {incident.message_text || incident.title}
            </p>
          </div>

          <div className="flex flex-col items-end gap-2 text-right shrink-0">
            <div className="text-sm text-gray-400">Total Signals</div>
            <div className="text-4xl font-bold text-blue-400">{incident.signal_count}</div>
            <div className="text-xs text-gray-500">
              Source: <span className="text-gray-300 capitalize">{incident.source || 'unknown'}</span>
            </div>
          </div>
        </div>

        {/* Timestamps row */}
        <div className="mt-5 pt-4 border-t border-white/5 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <TimeField label="Detected" value={incident.created_at} />
          <TimeField label="Acknowledged" value={incident.acknowledged_at} />
          <TimeField label="Resolved" value={incident.resolved_at} />
          <TimeField label="Closed" value={incident.closed_at} />
        </div>

        {/* Resolution note */}
        {incident.resolution_note && (
          <div className="mt-4 p-3 bg-green-500/10 border border-green-500/20 rounded-xl">
            <p className="text-xs text-green-400 font-semibold mb-1 flex items-center gap-1">
              <CheckCircle className="w-3 h-3" /> Resolution Note
            </p>
            <p className="text-sm text-green-300">{incident.resolution_note}</p>
          </div>
        )}
      </div>

      {/* Two-column: timeline + notifications */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* Audit Timeline */}
        <div className="glass-panel rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-white/5 bg-white/3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-400" />
            <h2 className="text-sm font-semibold">Incident Timeline</h2>
            <span className="ml-auto text-xs text-gray-500">{audit_log.length} events</span>
          </div>
          <div className="p-4 max-h-80 overflow-y-auto custom-scrollbar">
            {audit_log.length === 0 ? (
              <p className="text-center text-gray-500 text-sm py-8">No audit entries yet</p>
            ) : (
              <div className="relative">
                <div className="absolute left-3 top-0 bottom-0 w-px bg-white/10" />
                <div className="space-y-4">
                  {audit_log.map((entry, idx) => (
                    <AuditEntry key={entry.id} entry={entry} isLast={idx === audit_log.length - 1} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Notifications */}
        <div className="glass-panel rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-white/5 bg-white/3 flex items-center gap-2">
            <Mail className="w-4 h-4 text-blue-400" />
            <h2 className="text-sm font-semibold">Email Notifications</h2>
            <span className="ml-auto text-xs text-gray-500">{notifications.length} sent</span>
          </div>
          <div className="divide-y divide-white/5 max-h-80 overflow-y-auto custom-scrollbar">
            {notifications.length === 0 ? (
              <div className="text-center text-gray-500 text-sm py-8">No emails sent yet</div>
            ) : (
              notifications.map(notif => (
                <NotificationRow key={notif.id} notification={notif} />
              ))
            )}
          </div>
        </div>
      </div>

      {/* Resolve Modal */}
      {showResolve && (
        <ResolveModal
          incident={incident}
          onClose={() => setShowResolve(false)}
          onSuccess={async () => {
            setShowResolve(false);
            await loadDetail();
          }}
        />
      )}
    </div>
  );
};

// ─── Sub-components ───────────────────────────────────────────────────────────

const TimeField: React.FC<{ label: string; value: string | null }> = ({ label, value }) => (
  <div>
    <p className="text-gray-500 mb-0.5">{label}</p>
    {value ? (
      <>
        <p className="text-gray-200 font-medium">{format(new Date(value), 'HH:mm:ss')}</p>
        <p className="text-gray-500">{format(new Date(value), 'MMM dd')}</p>
      </>
    ) : (
      <p className="text-gray-600">—</p>
    )}
  </div>
);

const AuditEntry: React.FC<{ entry: AuditEntry; isLast: boolean }> = ({ entry, isLast }) => {
  const getActionColor = (action: string) => {
    switch (action) {
      case 'created':      return 'text-gray-400 bg-gray-500/20 border-gray-500/30';
      case 'state_change': return 'text-blue-400 bg-blue-500/20 border-blue-500/30';
      case 'escalation':   return 'text-red-400 bg-red-500/20 border-red-500/30';
      case 'reminder':     return 'text-yellow-400 bg-yellow-500/20 border-yellow-500/30';
      case 'rca_submitted':return 'text-green-400 bg-green-500/20 border-green-500/30';
      default:             return 'text-gray-400 bg-gray-500/20 border-gray-500/30';
    }
  };

  const getActionIcon = (action: string) => {
    switch (action) {
      case 'created':       return '🆕';
      case 'state_change':  return '🔄';
      case 'escalation':    return '🚨';
      case 'reminder':      return '⏰';
      case 'rca_submitted': return '✅';
      default:              return '📋';
    }
  };

  return (
    <div className="flex gap-3 relative pl-8">
      <div className="absolute left-1.5 top-1 w-3 h-3 rounded-full bg-gray-700 border-2 border-blue-500/50 z-10" />
      <div className="flex-1 pb-1">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <span className={clsx('text-xs px-2 py-0.5 rounded border font-medium', getActionColor(entry.action))}>
            {getActionIcon(entry.action)} {entry.action.replace('_', ' ')}
          </span>
          {entry.old_status && entry.new_status && (
            <span className="text-xs text-gray-500 flex items-center gap-1">
              {entry.old_status} <ChevronRight className="w-3 h-3" /> {entry.new_status}
            </span>
          )}
        </div>
        <p className="text-xs text-gray-500">{entry.notes}</p>
        <p className="text-xs text-gray-600 mt-0.5">
          {format(new Date(entry.timestamp), 'HH:mm:ss')} • {entry.performed_by}
        </p>
      </div>
    </div>
  );
};

const NotificationRow: React.FC<{ notification: Notification }> = ({ notification }) => (
  <div className="px-5 py-3">
    <div className="flex items-start justify-between gap-2">
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-gray-200 truncate">{notification.subject}</p>
        <p className="text-xs text-gray-500 mt-0.5">To: {notification.email_to}</p>
      </div>
      <span className={clsx(
        'text-xs px-2 py-0.5 rounded border shrink-0',
        notification.status === 'sent'
          ? 'bg-green-500/10 text-green-400 border-green-500/20'
          : 'bg-red-500/10 text-red-400 border-red-500/20'
      )}>
        {notification.status}
      </span>
    </div>
    <p className="text-xs text-gray-600 mt-1">
      {formatDistanceToNow(new Date(notification.sent_at), { addSuffix: true })}
    </p>
  </div>
);