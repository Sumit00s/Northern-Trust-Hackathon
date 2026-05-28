import React, { useState } from 'react';
import { X, FileText, CheckCircle } from 'lucide-react';
import { resolveIncident, type Incident } from '../api';

interface ResolveModalProps {
    incident: Incident;
    onClose: () => void;
    onSuccess: () => void;
}

export const ResolveModal: React.FC<ResolveModalProps> = ({ incident, onClose, onSuccess }) => {
    const [note, setNote] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (note.trim().length < 5) {
            setError('Resolution note must be at least 5 characters.');
            return;
        }
        setLoading(true);
        setError('');
        try {
            await resolveIncident(incident.id, note.trim());
            onSuccess();
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : 'Failed to resolve incident';
            setError(msg);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div
            className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={onClose}
        >
            <div
                className="bg-[#0f1117] w-full max-w-md rounded-2xl shadow-2xl border border-white/10 overflow-hidden animate-in zoom-in-95 duration-200"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="px-5 py-4 border-b border-white/5 flex justify-between items-center bg-green-500/5">
                    <h2 className="text-base font-bold flex items-center gap-2 text-green-400">
                        <CheckCircle className="w-4 h-4" />
                        Resolve Incident
                    </h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-5 space-y-4">
                    {/* Incident summary */}
                    <div className="bg-white/5 rounded-xl p-3 border border-white/10">
                        <p className="text-xs text-gray-400 mb-1">Resolving</p>
                        <p className="text-sm font-semibold text-white truncate">
                            {incident.service || incident.component_id}
                        </p>
                        <p className="text-xs text-gray-500 truncate mt-0.5">
                            {incident.message_text || incident.title}
                        </p>
                    </div>

                    {/* Resolution note */}
                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-1.5 flex items-center gap-1.5">
                            <FileText className="w-4 h-4 text-gray-400" />
                            Resolution Note <span className="text-red-400">*</span>
                        </label>
                        <textarea
                            required
                            rows={4}
                            value={note}
                            onChange={e => { setNote(e.target.value); setError(''); }}
                            placeholder="Describe how you resolved this incident..."
                            className="w-full bg-black/30 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-green-500/50 focus:ring-1 focus:ring-green-500/20 resize-none transition-all"
                        />
                    </div>

                    {error && (
                        <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 px-3 py-2 rounded-lg">
                            {error}
                        </p>
                    )}

                    {/* Buttons */}
                    <div className="flex justify-end gap-3 pt-2">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 rounded-lg text-sm font-medium text-gray-400 hover:text-white transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={loading}
                            className="px-5 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-sm font-semibold text-white flex items-center gap-2 transition-colors disabled:opacity-50"
                        >
                            <CheckCircle className="w-4 h-4" />
                            {loading ? 'Resolving...' : 'Mark as Resolved'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};