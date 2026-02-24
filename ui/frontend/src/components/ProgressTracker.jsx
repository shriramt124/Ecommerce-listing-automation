import { CheckCircle2, CircleDashed, CircleDot, ImageIcon } from 'lucide-react'

const STAGES = ['Image Analysis', 'Keyword Discovery', 'Title Optimization', 'Content Generation', 'Image Generation']

function stageIdx(name) {
    const s = (name || '').toLowerCase()
    if (s.includes('image anal')) return 0
    if (s.includes('keyword')) return 1
    if (s.includes('title')) return 2
    if (s.includes('content') || s.includes('bullet') || s.includes('desc')) return 3
    if (s.includes('image gen') || s.includes('lifestyle') || s.includes('banner') || s.includes('why')) return 4
    return -1
}

export default function ProgressTracker({ progress, jobStatus, outputDir, onOpenGallery }) {
    const current = progress?.product || 0
    const total = progress?.total || 0
    const pct = total > 0 ? Math.round((current / total) * 100) : 0
    const stage = stageIdx(progress?.stage || '')

    const StatusBadge = () => {
        if (!jobStatus) return null

        let colorCls = 'bg-prime-hover text-prime-text border-prime-border'
        let dotCls = 'bg-prime-muted'

        if (jobStatus === 'running') { colorCls = 'bg-prime-warningBg text-prime-warning border-prime-warning/30'; dotCls = 'bg-prime-warning animate-pulse' }
        if (jobStatus === 'done') { colorCls = 'bg-prime-successBg text-prime-success border-prime-success/30'; dotCls = 'bg-prime-success' }
        if (jobStatus === 'error') { colorCls = 'bg-prime-dangerBg text-prime-danger border-prime-danger/30'; dotCls = 'bg-prime-danger' }

        return (
            <div className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border text-[10px] font-bold uppercase tracking-wider ${colorCls}`}>
                <div className={`w-1.5 h-1.5 rounded-full ${dotCls}`} />
                {jobStatus}
            </div>
        )
    }

    return (
        <div className="px-6 py-5 bg-prime-surface border-b border-prime-divider shrink-0 flex flex-col gap-4">

            {/* Header Row */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <h2 className="text-[14px] font-semibold text-prime-text tracking-tight">Pipeline Progress</h2>
                    <StatusBadge />
                </div>

                {progress && (
                    <div className="flex items-center gap-2 text-[12px]">
                        <span className="text-prime-muted">Processing:</span>
                        <span className="font-mono bg-prime-bg border border-prime-border px-1.5 py-0.5 rounded text-prime-text">{progress.asin || 'init...'}</span>
                        <span className="text-prime-muted ml-2">Item</span>
                        <span className="font-bold text-prime-text">{current} <span className="text-prime-muted font-normal">/ {total}</span></span>
                    </div>
                )}
            </div>

            {/* Main Content Area */}
            {progress ? (
                <div className="space-y-5">
                    {/* Progress Bar */}
                    <div className="relative pt-1">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-[11px] font-bold text-prime-accent uppercase tracking-widest">{pct}% Complete</span>
                        </div>
                        <div className="overflow-hidden h-1.5 mb-4 text-xs flex rounded-full bg-prime-bg border border-prime-border/50">
                            <div
                                style={{ width: `${pct}%` }}
                                className="shadow-glow-success flex flex-col text-center whitespace-nowrap text-white justify-center bg-prime-success transition-all duration-500 ease-out"
                            />
                        </div>
                    </div>

                    {/* Stepper */}
                    <div className="flex items-center justify-between max-w-2xl">
                        {STAGES.map((s, i) => {
                            const isPast = i < stage
                            const isCurrent = i === stage
                            const isFuture = i > stage

                            return (
                                <div key={s} className="flex flex-col items-center gap-2 relative z-10">
                                    <div className={`w-6 h-6 rounded-full flex items-center justify-center transition-all duration-300 bg-prime-bg
                    ${isPast ? 'text-prime-success' : isCurrent ? 'text-prime-warning shadow-glow-subtle hidden sm:flex' : 'text-prime-label'}`}>
                                        {isPast ? <CheckCircle2 size={16} /> : isCurrent ? <CircleDot size={16} className="animate-pulse" /> : <CircleDashed size={14} />}
                                    </div>
                                    <span className={`text-[10px] uppercase tracking-wider font-semibold transition-colors
                    ${isPast ? 'text-prime-text' : isCurrent ? 'text-prime-warning' : 'text-prime-label'}`}>
                                        {s}
                                    </span>
                                </div>
                            )
                        })}
                    </div>
                </div>
            ) : (
                <div className="h-[88px] flex flex-col items-center justify-center border border-dashed border-prime-divider rounded-xl bg-prime-bg/50">
                    <span className="text-[13px] text-prime-muted">
                        {jobStatus === 'done' ? 'Pipeline execution finished successfully.' : 'Configure parameters and start a run to see live progress.'}
                    </span>
                </div>
            )}

            {/* Post-Run Actions */}
            {(jobStatus === 'done' || outputDir) && (
                <div className="pt-2 animate-in fade-in slide-in-from-top-2 duration-500">
                    <button onClick={onOpenGallery}
                        className="w-full flex items-center justify-center gap-2 bg-prime-bg border border-prime-divider text-prime-text py-2.5 rounded-lg text-[13px] font-medium hover:border-prime-primary hover:text-prime-primary hover:bg-prime-primaryBg transition-all shadow-sm">
                        <ImageIcon size={16} />
                        View Generated Gallery
                    </button>
                </div>
            )}
        </div>
    )
}
