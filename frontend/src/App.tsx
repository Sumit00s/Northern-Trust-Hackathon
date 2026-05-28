import React, { useState, useCallback } from 'react';
import { ShieldAlert, Activity, Wifi } from 'lucide-react';
import { Dashboard } from './components/Dashboard';
import { IncidentDetail } from './components/IncidentDetail';
import type { Incident } from './api';

type View = 'dashboard' | 'detail';

function App() {
  const [view, setView] = useState<View>('dashboard');
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);

  const handleSelectIncident = useCallback((incident: Incident) => {
    setSelectedIncident(incident);
    setView('detail');
  }, []);

  const handleBack = useCallback(() => {
    setSelectedIncident(null);
    setView('dashboard');
  }, []);

  return (
    <div className="min-h-screen relative overflow-hidden bg-background">
      {/* Ambient background glow */}
      <div className="fixed top-[-20%] left-[-10%] w-[60%] h-[60%] rounded-full bg-blue-900/20 blur-[140px] pointer-events-none" />
      <div className="fixed bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-red-900/10 blur-[140px] pointer-events-none" />

      {/* Top Navbar */}
      <nav className="relative z-10 glass-panel sticky top-0 w-full border-b border-white/5 py-3 px-6 md:px-10 flex justify-between items-center bg-background/85 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <div className="p-1.5 rounded-lg bg-blue-500/20 border border-blue-500/30">
            <ShieldAlert className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white leading-none">
              IMS <span className="font-light text-gray-400">| Mission Control</span>
            </h1>
            <p className="text-xs text-gray-500">Incident Management System</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            <span>Live</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-gray-500 bg-white/5 px-3 py-1.5 rounded-lg border border-white/10">
            <Wifi className="w-3 h-3" />
            <span>Polling every 5s</span>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="relative z-10 max-w-[1400px] mx-auto px-4 md:px-6 py-6">
        {view === 'dashboard' ? (
          <Dashboard onSelectIncident={handleSelectIncident} />
        ) : selectedIncident ? (
          <IncidentDetail
            incidentId={selectedIncident.id}
            onBack={handleBack}
          />
        ) : null}
      </main>
    </div>
  );
}

export default App;
