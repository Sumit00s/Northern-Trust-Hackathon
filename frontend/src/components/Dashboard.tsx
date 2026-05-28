import React, { useEffect, useState, useCallback } from 'react';
import {
  Activity, AlertTriangle, CheckCircle, Clock, Server, Code2,
  TriangleAlert, Eye, Search, Zap, XCircle, ChevronRight,
  BarChart3, TrendingUp
} from 'lucide-react';
import clsx from 'clsx';
import { formatDistanceToNow } from 'date-fns';
import {
  fetchIncidents, fetchAnalytics, fetchHealth,
  acknowledgeIncident, investigateIncident, closeIncident,
  type Incident, type Analytics, type Health
} from '../api';
import { ResolveModal } from './ResolveModal';

interface DashboardProps {
  onSelectIncident: (incident: Incident) => void;
}

// ─── Severity helpers ─────────────────────────────────────────────────────────

export const getSeverityBg = (severity: string) => {
  switch (severity) {
    case 'P0': return 'bg-red-600 text-white border-red-500';
    case 'P1': return 'bg-red-500 text-white border-red-400';
    case 'P2': return 'bg-orange-500 text-white border-orange-400';
    case 'P3': return 'bg-yellow-500 text-black border-yellow-400';
    case 'P4': return 'bg-blue-500 text-white border-blue-400';
    default:   return 'bg-gray-600 text-white border-gray-500';
  }
};

export const getSeverityRowBg = (severity: string) => {
  switch (severity) {
    case 'P0':
    case 'P1': return 'border-l-4 border-l-red-500/70';
    case 'P2': return 'border-l-4 border-l-orange-500/70';
    case 'P3': return 'border-l-4 border-l-yellow-500/70';
    case 'P4': return 'border-l-4 border-l-blue-500/70';
    default:   return 'border-l-4 border-l-gray-600/50';
  }
};

export const getStatusStyle = (status: string) => {
  switch (status) {
    case 'DETECTED':     return { bg: 'bg-red-500/15 text-red-400 border-red-500/30', dot: 'bg-red-400 animate-pulse' };
    case 'ACKNOWLEDGED': return { bg: 'bg-orange-500/15 text-orange-400 border-orange-500/30', dot: 'bg-orange-400' };
    case 'INVESTIGATING':return { bg: 'bg-blue-500/15 text-blue-400 border-blue-500/30', dot: 'bg-blue-400 animate-pulse' };
    case 'RESOLVED':     return { bg: 'bg-green-500/15 text-green-400 border-green-500/30', dot: 'bg-green-400' };
    case 'CLOSED':       return { bg: 'bg-gray-500/15 text-gray-400 border-gray-500/30', dot: 'bg-gray-400' };
    default:             return { bg: 'bg-gray-500/15 text-gray-400 border-gray-500/30', dot: 'bg-gray-400' };
  }
};

// ─── Dashboard Component ──────────────────────────────────────────────────────

export const Dashboard: React.FC<DashboardProps> = ({ onSelectIncident }) => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [resolveTarget, setResolveTarget] = useState<Incident | null>(null);
  const [filter, setFilter] = useState<'all' | 'infrastructure' | 'application' | 'active'>('active');
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const loadData = useCallback(async () => {
    try {
      const [inc, ana, h] = await Promise.all([
        fetchIncidents(),
        fetchAnalytics(),
        fetchHealth(),
      ]);
      setIncidents(inc);
      setAnalytics(ana);
      setHealth(h);
      setLastUpdated(new Date());
    } catch (e) {
      console.error('Failed to load dashboard data', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleAction = async (
    e: React.MouseEvent,
    incidentId: string,
    action: 'acknowledge' | 'investigate' | 'resolve' | 'close',
    incident?: Incident
  ) => {
    e.stopPropagation();
    if (action === 'resolve' && incident) {
      setResolveTarget(incident);
      return;
    }

    setActionLoading(incidentId + action);
    try {
      if (action === 'acknowledge') await acknowledgeIncident(incidentId);
      else if (action === 'investigate') await investigateIncident(incidentId);
      else if (action === 'close') await closeIncident(incidentId);
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Action failed';
      alert(msg);
    } finally {
      setActionLoading(null);
    }
  };

  const filteredIncidents = incidents.filter(i => {
    if (filter === 'active') return !['RESOLVED', 'CLOSED'].includes(i.status);
    if (filter === 'infrastructure') return i.incident_type === 'infrastructure';
    if (filter === 'application') return i.incident_type === 'application';
    return true;
  });

  const activeCount = incidents.filter(i => !['RESOLVED', 'CLOSED'].includes(i.status)).length;
  const criticalCount = incidents.filter(i =>
    ['P1', 'P0'].includes(i.severity) &&
    i.incident_type === 'infrastructure' &&
    !['RESOLVED', 'CLOSED'].includes(i.status)
  ).length;
  const resolvedToday = analytics?.resolved_today ?? 0;
  const mttrMinutes = analytics?.avg_mttr_seconds
    ? Math.round(analytics.avg_mttr_seconds / 60)
    : null;

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Active Incidents"
          value={activeCount}
          icon={<AlertTriangle className="w-5 h-5" />}
          color="orange"
          pulse={activeCount > 0}
        />
        <StatCard
          label="Critical (Infra)"
          value={criticalCount}
          icon={<Zap className="w-5 h-5" />}
          color="red"
          pulse={criticalCount > 0}
        />
        <StatCard
          label="Resolved Today"
          value={resolvedToday}
          icon={<CheckCircle className="w-5 h-5" />}
          color="green"
        />
        <StatCard
          label="Avg MTTR"
          value={mttrMinutes !== null ? `${mttrMinutes}m` : '—'}
          icon={<TrendingUp className="w-5 h-5" />}
          color="blue"
        />
      </div>

      {/* Secondary stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(['DETECTED', 'ACKNOWLEDGED', 'INVESTIGATING', 'RESOLVED'] as const).map(status => {
          const cnt = analytics?.counts_by_status?.[status] ?? 0;
          const style = getStatusStyle(status);
          return (
            <div key={status} className={clsx('glass-panel rounded-xl p-4 flex items-center justify-between border', style.bg.split(' ')[0].replace('bg-', 'border-').replace('/15', '/20'))}>
              <div>
                <div className="text-xs text-gray-400 font-medium mb-0.5">{status}</div>
                <div className="text-2xl font-bold">{cnt}</div>
              </div>
              <div className={clsx('w-2.5 h-2.5 rounded-full', style.dot)} />
            </div>
          );
        })}
      </div>

      {/* Filter + Table */}
      <div className="glass-panel rounded-xl overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/5 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 bg-white/3">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-semibold">Incident Feed</h2>
            <span className="text-xs bg-white/10 px-2 py-0.5 rounded-full text-gray-400">
              {filteredIncidents.length}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex bg-white/5 rounded-lg p-1 gap-1">
              {(['active', 'all', 'infrastructure', 'application'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={clsx(
                    'px-3 py-1.5 rounded-md text-xs font-medium transition-all capitalize',
                    filter === f
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-400 hover:text-white hover:bg-white/10'
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
            <span className="text-xs text-gray-500">
              Updated {formatDistanceToNow(lastUpdated, { addSuffix: true })}
            </span>
          </div>
        </div>

        {/* Incident rows */}
        <div className="divide-y divide-white/5 max-h-[65vh] overflow-y-auto custom-scrollbar">
          {loading ? (
            <div className="py-16 text-center text-gray-500">
              <Activity className="w-8 h-8 mx-auto mb-3 animate-spin text-blue-400" />
              <p>Loading incidents...</p>
            </div>
          ) : filteredIncidents.length === 0 ? (
            <div className="py-16 text-center text-gray-500">
              <CheckCircle className="w-12 h-12 mx-auto mb-3 opacity-20" />
              <p className="font-medium">No incidents match this filter</p>
              <p className="text-sm mt-1">System is running smoothly 🎉</p>
            </div>
          ) : (
            filteredIncidents.map(incident => (
              <IncidentRow
                key={incident.id}
                incident={incident}
                actionLoading={actionLoading}
                onSelect={onSelectIncident}
                onAction={handleAction}
              />
            ))
          )}
        </div>
      </div>

      {/* Analytics section */}
      {analytics && analytics.incidents_by_service.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Service frequency */}
          <div className="glass-panel rounded-xl p-5">
            <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2 mb-4">
              <BarChart3 className="w-4 h-4 text-blue-400" /> Incidents by Service
            </h3>
            <div className="space-y-2">
              {analytics.incidents_by_service.slice(0, 6).map(s => (
                <div key={s.service} className="flex items-center gap-3">
                  <span className={clsx('text-xs font-bold px-1.5 py-0.5 rounded border', getSeverityBg(s.max_severity))}>
                    {s.max_severity}
                  </span>
                  <span className="text-sm text-gray-300 flex-1 truncate">{s.service}</span>
                  <span className="text-sm font-bold text-white">{s.count}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Type split */}
          <div className="glass-panel rounded-xl p-5">
            <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2 mb-4">
              <TrendingUp className="w-4 h-4 text-blue-400" /> Type Distribution
            </h3>
            <div className="space-y-4">
              {Object.entries(analytics.incidents_by_type).map(([type, count]) => {
                const total = Object.values(analytics.incidents_by_type).reduce((a, b) => a + b, 0);
                const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                return (
                  <div key={type}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-300 capitalize flex items-center gap-1.5">
                        {type === 'infrastructure' ? <Server className="w-3.5 h-3.5 text-red-400" /> : <Code2 className="w-3.5 h-3.5 text-blue-400" />}
                        {type}
                      </span>
                      <span className="text-gray-400">{count} ({pct}%)</span>
                    </div>
                    <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className={clsx('h-full rounded-full transition-all duration-500', type === 'infrastructure' ? 'bg-red-500' : 'bg-blue-500')}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Resolve Modal */}
      {resolveTarget && (
        <ResolveModal
          incident={resolveTarget}
          onClose={() => setResolveTarget(null)}
          onSuccess={async () => {
            setResolveTarget(null);
            await loadData();
          }}
        />
      )}
    </div>
  );
};

// ─── Stat Card ────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  color: 'red' | 'orange' | 'green' | 'blue';
  pulse?: boolean;
}

const colorMap = {
  red:    { bg: 'bg-red-500/10',    border: 'border-red-500/20',    text: 'text-red-400',    icon: 'bg-red-500/20 border-red-500/30' },
  orange: { bg: 'bg-orange-500/10', border: 'border-orange-500/20', text: 'text-orange-400', icon: 'bg-orange-500/20 border-orange-500/30' },
  green:  { bg: 'bg-green-500/10',  border: 'border-green-500/20',  text: 'text-green-400',  icon: 'bg-green-500/20 border-green-500/30' },
  blue:   { bg: 'bg-blue-500/10',   border: 'border-blue-500/20',   text: 'text-blue-400',   icon: 'bg-blue-500/20 border-blue-500/30' },
};

const StatCard: React.FC<StatCardProps> = ({ label, value, icon, color, pulse }) => {
  const c = colorMap[color];
  return (
    <div className={clsx('glass-panel rounded-xl p-5 border', c.bg, c.border)}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-2">{label}</p>
          <p className={clsx('text-3xl font-bold', c.text)}>{value}</p>
        </div>
        <div className={clsx('p-2 rounded-lg border relative', c.icon)}>
          <span className={c.text}>{icon}</span>
          {pulse && (
            <span className={clsx('absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full animate-ping', c.text.replace('text-', 'bg-').replace('-400', '-400'))} />
          )}
        </div>
      </div>
    </div>
  );
};

// ─── Incident Row ─────────────────────────────────────────────────────────────

interface IncidentRowProps {
  incident: Incident;
  actionLoading: string | null;
  onSelect: (i: Incident) => void;
  onAction: (e: React.MouseEvent, id: string, action: 'acknowledge' | 'investigate' | 'resolve' | 'close', incident?: Incident) => void;
}

const IncidentRow: React.FC<IncidentRowProps> = ({ incident, actionLoading, onSelect, onAction }) => {
  const statusStyle = getStatusStyle(incident.status);
  const isInfra = incident.incident_type === 'infrastructure';

  return (
    <div
      className={clsx(
        'px-5 py-4 hover:bg-white/3 cursor-pointer transition-all group',
        getSeverityRowBg(incident.severity)
      )}
      onClick={() => onSelect(incident)}
    >
      <div className="flex items-start gap-4">
        {/* Severity + Type badges */}
        <div className="flex flex-col items-center gap-1.5 pt-0.5 min-w-[48px]">
          <span className={clsx('px-2 py-0.5 rounded-md text-xs font-bold border', getSeverityBg(incident.severity))}>
            {incident.severity}
          </span>
          <span className={clsx(
            'px-1.5 py-0.5 rounded text-[10px] font-medium border',
            isInfra
              ? 'bg-red-500/10 text-red-400 border-red-500/30'
              : 'bg-blue-500/10 text-blue-400 border-blue-500/30'
          )}>
            {isInfra ? 'INFRA' : 'APP'}
          </span>
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {isInfra
              ? <Server className="w-3.5 h-3.5 text-gray-400 shrink-0" />
              : <Code2 className="w-3.5 h-3.5 text-gray-400 shrink-0" />}
            <span className="font-semibold text-gray-100 truncate group-hover:text-white transition-colors text-sm">
              {incident.service || incident.component_id}
            </span>
            {incident.escalation_count > 0 && (
              <span className="text-[10px] bg-red-500/20 text-red-400 border border-red-500/30 px-1.5 py-0.5 rounded font-bold shrink-0">
                ESC ×{incident.escalation_count}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 truncate mb-2">
            {incident.message_text || incident.title}
          </p>
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDistanceToNow(new Date(incident.created_at), { addSuffix: true })}
            </span>
            <span className="flex items-center gap-1">
              <Activity className="w-3 h-3" />
              {incident.signal_count} signal{incident.signal_count !== 1 ? 's' : ''}
            </span>
            {incident.source && (
              <span className="bg-white/5 px-1.5 py-0.5 rounded capitalize">
                {incident.source}
              </span>
            )}
          </div>
        </div>

        {/* Status + Actions */}
        <div className="flex flex-col items-end gap-2 shrink-0">
          {/* Status badge */}
          <div className={clsx('flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium', statusStyle.bg)}>
            <div className={clsx('w-1.5 h-1.5 rounded-full', statusStyle.dot)} />
            {incident.status}
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-1.5" onClick={e => e.stopPropagation()}>
            {incident.status === 'DETECTED' && (
              <ActionButton
                label="Acknowledge"
                onClick={e => onAction(e, incident.id, 'acknowledge')}
                loading={actionLoading === incident.id + 'acknowledge'}
                color="orange"
              />
            )}
            {incident.status === 'ACKNOWLEDGED' && (
              <ActionButton
                label="Investigate"
                onClick={e => onAction(e, incident.id, 'investigate')}
                loading={actionLoading === incident.id + 'investigate'}
                color="blue"
              />
            )}
            {incident.status === 'INVESTIGATING' && (
              <ActionButton
                label="Resolve"
                onClick={e => onAction(e, incident.id, 'resolve', incident)}
                loading={actionLoading === incident.id + 'resolve'}
                color="green"
              />
            )}
            {incident.status === 'RESOLVED' && (
              <ActionButton
                label="Close"
                onClick={e => onAction(e, incident.id, 'close')}
                loading={actionLoading === incident.id + 'close'}
                color="gray"
              />
            )}
            <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-gray-400 transition-colors" />
          </div>
        </div>
      </div>
    </div>
  );
};

// ─── Action Button ─────────────────────────────────────────────────────────────

interface ActionButtonProps {
  label: string;
  onClick: (e: React.MouseEvent) => void;
  loading?: boolean;
  color: 'orange' | 'blue' | 'green' | 'gray' | 'red';
}

const actionButtonColors = {
  orange: 'bg-orange-500/15 text-orange-400 border-orange-500/40 hover:bg-orange-500/30',
  blue:   'bg-blue-500/15 text-blue-400 border-blue-500/40 hover:bg-blue-500/30',
  green:  'bg-green-500/15 text-green-400 border-green-500/40 hover:bg-green-500/30',
  gray:   'bg-gray-500/15 text-gray-400 border-gray-500/40 hover:bg-gray-500/30',
  red:    'bg-red-500/15 text-red-400 border-red-500/40 hover:bg-red-500/30',
};

const ActionButton: React.FC<ActionButtonProps> = ({ label, onClick, loading, color }) => (
  <button
    onClick={onClick}
    disabled={loading}
    className={clsx(
      'px-3 py-1 rounded-lg text-xs font-semibold border transition-all',
      actionButtonColors[color],
      loading && 'opacity-50 cursor-wait'
    )}
  >
    {loading ? '...' : label}
  </button>
);