import { useEffect, useRef, useState } from 'react'
import { Terminal, Trash2, ArrowDownToLine } from 'lucide-react'
import { WS_URL } from '../api/client'

// Enhanced regex-based colorizer that outputs actual HTML spans for precise coloring
function colorize(line) {
    if (!line) return { __html: '&nbsp;' }

    let html = line
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')

    // Base colors for typical log levels
    if (html.includes('❌') || html.includes('ERROR') || html.includes('Failed')) {
        return { __html: `<span class="text-prime-danger font-semibold">${html}</span>` }
    }
    if (html.includes('✅') || html.match(/\b(SUCCESS|done|complete)\b/i)) {
        return { __html: `<span class="text-prime-success">${html}</span>` }
    }
    if (html.includes('WARN') || html.includes('Skipping')) {
        return { __html: `<span class="text-prime-warning">${html}</span>` }
    }

    // Highlight specific keywords while keeping the rest neutral
    html = html
        .replace(/\b(Running|Processing|Generating|Brainstorming|Starting)\b/g, '<span class="text-prime-info font-medium">$1</span>')
        .replace(/\b(Amazon|AMAZON|Listing|ASIN)\b/g, '<span class="text-prime-accent font-bold">$1</span>')
        .replace(/(B0[A-Z0-9]{8})/g, '<span class="text-prime-primary bg-prime-primaryBg px-1 py-0.5 rounded">$1</span>') // Highlight ASINs
        .replace(/\[\d{2}:\d{2}:\d{2}\]/g, '<span class="text-prime-label">$1</span>') // Timestamps if any
        .replace(/═+/g, '<span class="text-prime-divider">$&</span>') // Separators

    return { __html: `<span class="text-prime-muted">${html}</span>` }
}

export default function LiveTerminal({ jobId, onProgress, onDone }) {
    const [lines, setLines] = useState([])
    const [autoScroll, setAutoScroll] = useState(true)
    const [connected, setConnected] = useState(false)
    const termRef = useRef(null)

    useEffect(() => {
        if (!jobId) return
        setLines([]); setConnected(false)
        const ws = new WebSocket(WS_URL(jobId))

        ws.onopen = () => setConnected(true)
        ws.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data)
                if (msg.type === 'log') setLines(prev => [...prev, msg.line])
                else if (msg.type === 'progress') onProgress?.(msg)
                else if (['done', 'error', 'stopped'].includes(msg.type)) { setConnected(false); onDone?.(msg) }
            } catch { }
        }
        ws.onclose = () => setConnected(false)
        ws.onerror = () => setConnected(false)
        return () => ws.close()
    }, [jobId])

    useEffect(() => {
        if (autoScroll && termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight
    }, [lines, autoScroll])

    return (
        <div className="flex flex-col flex-1 min-h-0 relative m-4 mt-0 rounded-xl overflow-hidden border border-prime-border shadow-2xl bg-[#050505]">

            {/* Mac-style Window Titlebar */}
            <div className="flex items-center justify-between px-4 py-2 bg-[#111111] border-b border-[#222] shrink-0">
                <div className="flex items-center gap-4">
                    {/* Traffic Lights */}
                    <div className="flex items-center gap-1.5 opacity-80">
                        <div className="w-3 h-3 rounded-full bg-[#FF5F56] border border-[#E0443E]" />
                        <div className="w-3 h-3 rounded-full bg-[#FFBD2E] border border-[#DEA123]" />
                        <div className="w-3 h-3 rounded-full bg-[#27C93F] border border-[#1AAB29]" />
                    </div>
                    <div className="flex items-center gap-2 text-[#777] text-[11px] font-mono tracking-widest uppercase">
                        <Terminal size={12} />
                        <span>Agentic Console</span>
                    </div>
                </div>

                {/* Status Indicator & Controls */}
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-1.5 text-[10px] font-bold tracking-widest uppercase pr-3 border-r border-[#333]">
                        {connected ? (
                            <><span className="w-1.5 h-1.5 rounded-full bg-prime-success shadow-[0_0_8px_#10B981] animate-pulse" /> <span className="text-prime-success">Streaming</span></>
                        ) : jobId ? (
                            <><span className="w-1.5 h-1.5 rounded-full bg-prime-label" /> <span className="text-prime-label">Disconnected</span></>
                        ) : (
                            <><span className="w-1.5 h-1.5 rounded-full bg-prime-divider" /> <span className="text-[#555]">Idle</span></>
                        )}
                    </div>

                    <div className="flex items-center gap-1.5">
                        <button
                            onClick={() => setAutoScroll(!autoScroll)}
                            className={`p-1.5 rounded flex items-center gap-1 text-[11px] transition-colors ${autoScroll ? 'bg-[#222] text-prime-accent' : 'text-[#666] hover:bg-[#1A1A1A] hover:text-[#999]'}`}
                            title="Toggle Auto-scroll">
                            <ArrowDownToLine size={13} />
                        </button>
                        <button
                            onClick={() => setLines([])}
                            className="p-1.5 rounded text-[#666] hover:bg-[#2A1515] hover:text-prime-danger transition-colors"
                            title="Clear Console">
                            <Trash2 size={13} />
                        </button>
                    </div>
                </div>
            </div>

            {/* Terminal Output Area */}
            <div ref={termRef} className="flex-1 overflow-y-auto px-5 py-4 font-mono text-[12px] leading-relaxed relative isolate">

                {/* Subtle background glow */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-prime-primary/5 rounded-full blur-[100px] -z-10 pointer-events-none" />

                {lines.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-[#444] space-y-3 font-sans">
                        <Terminal size={32} />
                        <p className="text-[13px]">Awaiting master pipeline execution...</p>
                    </div>
                ) : (
                    <div className="flex flex-col">
                        {lines.map((line, i) => (
                            <div
                                key={i}
                                className="whitespace-pre-wrap break-words hover:bg-white/[0.02] -mx-5 px-5 py-0.5"
                                dangerouslySetInnerHTML={colorize(line)}
                            />
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}
