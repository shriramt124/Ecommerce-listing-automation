import { useState, useEffect } from 'react'
import { getRuns } from '../api/client'
import { RotateCw, Play, Inbox, FolderOpen, Clock } from 'lucide-react'

const STATUS = {
    running: { cls: 'bg-prime-warningBg text-prime-warning border-prime-warning/30 shadow-[0_0_10px_-2px_rgba(245,158,11,0.2)]', dot: 'bg-prime-warning animate-pulse', label: 'Running' },
    done: { cls: 'bg-prime-successBg text-prime-success border-prime-success/30 shadow-[0_0_10px_-2px_rgba(16,185,129,0.2)]', dot: 'bg-prime-success', label: 'Done' },
    error: { cls: 'bg-prime-dangerBg text-prime-danger border-prime-danger/30 shadow-[0_0_10px_-2px_rgba(239,68,68,0.2)]', dot: 'bg-prime-danger', label: 'Error' },
    stopped: { cls: 'bg-prime-infoBg text-prime-info border-prime-info/30', dot: 'bg-prime-info', label: 'Stopped' },
    partial: { cls: 'bg-prime-warningBg text-prime-warning border-prime-warning/30', dot: 'bg-prime-warning', label: 'Partial' },
}

export default function RunHistory({ onOpenGallery }) {
    const [runs, setRuns] = useState([])
    const [loading, setLoading] = useState(true)

    const load = () => { setLoading(true); getRuns().then(setRuns).finally(() => setLoading(false)) }
    useEffect(() => { load() }, [])

    const s = (status) => STATUS[status] || { cls: 'bg-prime-bg text-prime-text border-prime-border', dot: 'bg-prime-muted', label: status }

    return (
        <div className="p-8 overflow-y-auto h-full bg-prime-bg custom-scrollbar relative">

            {/* Page Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h2 className="text-[18px] font-bold text-prime-text tracking-tight flex items-center gap-2">
                        <Clock className="text-prime-primary" size={20} />
                        Execution History
                    </h2>
                    <p className="text-[12px] text-prime-muted mt-1">Review past generations and their outputs.</p>
                </div>

                <button onClick={load} disabled={loading}
                    className="flex items-center gap-2 bg-prime-surface border border-prime-border text-prime-muted px-4 py-2 rounded-lg text-[13px] font-medium hover:text-prime-text hover:border-[#404040] transition-colors disabled:opacity-50">
                    <RotateCw size={14} className={loading ? "animate-spin" : ""} />
                    Refresh
                </button>
            </div>

            {loading && (
                <div className="flex flex-col items-center justify-center py-20 gap-4">
                    <div className="w-8 h-8 rounded-full border-2 border-prime-divider border-t-prime-primary animate-spin" />
                    <p className="text-[13px] text-prime-muted">Fetching history...</p>
                </div>
            )}

            {!loading && runs.length === 0 && (
                <div className="flex flex-col items-center justify-center py-32 border border-dashed border-prime-divider rounded-2xl bg-prime-surface/30">
                    <div className="w-12 h-12 rounded-full bg-prime-hover flex items-center justify-center mb-4">
                        <Inbox size={24} className="text-prime-label" />
                    </div>
                    <h3 className="text-[15px] font-medium text-prime-text mb-1">No Runs Found</h3>
                    <p className="text-[13px] text-prime-muted">Pipeline executions will appear here.</p>
                </div>
            )}

            {!loading && runs.length > 0 && (
                <div className="rounded-xl border border-prime-border bg-prime-surface overflow-hidden shadow-2xl">
                    <table className="w-full border-collapse">
                        <thead>
                            <tr className="bg-prime-bg border-b border-prime-border">
                                {['Run Name', 'Success Rate', 'Status', 'Timestamp', 'Action'].map(h => (
                                    <th key={h} className="text-left text-[11px] font-bold text-prime-label px-5 py-3.5 uppercase tracking-widest whitespace-nowrap">{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-prime-divider">
                            {runs.map(run => (
                                <tr key={run.id} className="hover:bg-prime-hover/80 transition-colors group">
                                    <td className="px-5 py-4 text-[13px] text-prime-accent font-semibold max-w-[280px] truncate" title={run.outputDir}>
                                        {run.name || run.id}
                                    </td>
                                    <td className="px-5 py-4">
                                        <div className="flex items-center gap-2">
                                            <div className="w-full max-w-[80px] h-1.5 bg-prime-bg rounded-full overflow-hidden border border-prime-divider hidden sm:block">
                                                <div
                                                    className="h-full bg-prime-success transition-all duration-500 shadow-glow-success"
                                                    style={{ width: `${run.total > 0 ? (run.successCount / run.total) * 100 : 0}%` }}
                                                />
                                            </div>
                                            <span className="text-[12px] text-prime-success font-medium tracking-wide">
                                                {run.total > 0 ? `${run.successCount}/${run.total}` : '—'}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-5 py-4">
                                        <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border ${s(run.status).cls}`}>
                                            <div className={`w-1.5 h-1.5 rounded-full ${s(run.status).dot}`} />
                                            {s(run.status).label}
                                        </div>
                                    </td>
                                    <td className="px-5 py-4 text-[12px] text-prime-muted whitespace-nowrap font-mono tracking-tight">
                                        {run.startedAt ? new Date(run.startedAt).toLocaleString(undefined, {
                                            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                                        }) : <span className="opacity-50">—</span>}
                                    </td>
                                    <td className="px-5 py-4">
                                        <button
                                            onClick={() => onOpenGallery(run.id)}
                                            className="flex items-center gap-2 bg-prime-bg border border-prime-border text-prime-text px-4 py-1.5 rounded-md text-[12px] font-medium hover:border-prime-primary hover:text-prime-primary hover:bg-prime-primaryBg transition-all shadow-sm opacity-80 group-hover:opacity-100"
                                        >
                                            <FolderOpen size={14} /> Open
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    )
}
