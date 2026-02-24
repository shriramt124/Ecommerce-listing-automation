import React, { useState, useEffect, useRef } from 'react';
import { Brain, Database, Cpu, Search, Type, ListEnd, Sparkles, AlertTriangle, CheckCircle2, Network } from 'lucide-react';

const AGENT_ICONS = {
    CategoryDetectorAgent: Database,
    ConceptEvaluatorAgent: Brain,
    KeywordSelectorAgent: Search,
    QueryPlannerAgent: Cpu,
    TitleComposerAgent: Type,
    TitleExtenderAgent: ListEnd,
    BulletPointAgent: Sparkles,
    SearchTermsAgent: Search,
    DescriptionAgent: Type,
    NeuralMemory: Network
};

const AGENT_COLORS = {
    CategoryDetectorAgent: "text-blue-400 border-blue-400/30 bg-blue-400/10",
    ConceptEvaluatorAgent: "text-purple-400 border-purple-400/30 bg-purple-400/10",
    KeywordSelectorAgent: "text-amber-400 border-amber-400/30 bg-amber-400/10",
    QueryPlannerAgent: "text-cyan-400 border-cyan-400/30 bg-cyan-400/10",
    TitleComposerAgent: "text-emerald-400 border-emerald-400/30 bg-emerald-400/10",
    TitleExtenderAgent: "text-teal-400 border-teal-400/30 bg-teal-400/10",
    BulletPointAgent: "text-pink-400 border-pink-400/30 bg-pink-400/10",
    SearchTermsAgent: "text-orange-400 border-orange-400/30 bg-orange-400/10",
    DescriptionAgent: "text-indigo-400 border-indigo-400/30 bg-indigo-400/10",
    NeuralMemory: "text-rose-400 border-rose-400/30 bg-rose-400/10"
};

export default function AIVisualizer({ jobId }) {
    const [activeAgent, setActiveAgent] = useState(null);
    const [logs, setLogs] = useState([]);
    const wsRef = useRef(null);

    useEffect(() => {
        // If we have an active job, connect to telemetry stream
        if (!jobId) return;

        // Connect to WebSocket
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const baseUrl = window.location.hostname === 'localhost' ? 'localhost:8000' : window.location.host;
        const wsUrl = `${protocol}//${baseUrl}/ws/telemetry`;

        wsRef.current = new WebSocket(wsUrl);

        wsRef.current.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === "agent_telemetry") {

                    if (msg.action === "start") {
                        setActiveAgent(msg.agent);
                    } else if (msg.action === "complete") {
                        setTimeout(() => {
                            setActiveAgent(prev => prev === msg.agent ? null : prev);
                        }, 1000);
                    } else if (msg.action === "memory_injection") {
                        setActiveAgent(msg.agent);
                        setTimeout(() => {
                            setActiveAgent(prev => prev === msg.agent ? null : prev);
                        }, 2500);
                    }

                    setLogs(prev => {
                        const newLogs = [...prev, msg].slice(-20); // Keep last 20 events
                        return newLogs;
                    });
                }
            } catch (err) {
                console.error("Telemetry parse err", err);
            }
        };

        return () => {
            if (wsRef.current) wsRef.current.close();
        };
    }, [jobId]);

    return (
        <div className="flex flex-col h-full bg-prime-bg border-prime-divider border-t overflow-hidden">
            <div className="px-4 py-2 bg-prime-surface/80 border-b border-prime-divider flex items-center gap-2">
                <Brain size={16} className="text-prime-primary" />
                <h3 className="text-[13px] font-semibold tracking-tight text-prime-text">Neural Dashboard</h3>
                {activeAgent && (
                    <span className="ml-auto text-xs text-prime-primary tracking-wider animate-pulse font-mono">
                        [ {activeAgent} WORKING ]
                    </span>
                )}
            </div>

            {/* Node Map Visualization */}
            <div className="shrink-0 p-4 grid grid-cols-3 sm:grid-cols-4 xl:grid-cols-5 gap-3 content-start relative z-10 shadow-sm bg-prime-surface/10">
                {Object.entries(AGENT_ICONS).map(([agentId, Icon]) => {
                    const isActive = activeAgent === agentId;
                    const isRetry = isActive && logs.length > 0 && logs[logs.length - 1].action === 'retry' && logs[logs.length - 1].agent === agentId;

                    let ringClass = "border-prime-divider bg-prime-surface/30 opacity-60";
                    if (isActive) {
                        ringClass = isRetry
                            ? "border-amber-500 shadow-[0_0_15px_-3px_rgba(245,158,11,0.5)] bg-amber-500/10"
                            : `${AGENT_COLORS[agentId]} shadow-[0_0_15px_-3px_currentColor]`;
                    }

                    return (
                        <div key={agentId} className={`flex flex-col items-center justify-center p-2.5 rounded-lg border transition-all duration-300 relative ${ringClass}`}>
                            <Icon size={18} className={`mb-1.5 ${isActive ? (isRetry ? 'text-amber-500' : 'text-current') : 'text-prime-muted'}`} />
                            <div className="text-[10px] text-center font-medium truncate w-full text-prime-text">
                                {agentId.replace('Agent', '')}
                            </div>
                            {isRetry && <span className="absolute top-1 right-2 text-amber-500 text-[8px] font-bold tracking-widest animate-pulse border border-amber-500/30 bg-amber-500/10 px-1 rounded">RETRY</span>}
                        </div>
                    );
                })}
            </div>

            {/* Thought Stream Panel */}
            <div className="flex-1 border-t border-prime-divider bg-[#0A0A0A] p-4 overflow-y-auto font-mono text-[11px] leading-relaxed custom-scrollbar shadow-inner">
                {logs.map((log, i) => {
                    const isRetry = log.action === 'retry';
                    return (
                        <div key={i} className={`mb-1.5 flex gap-2 ${isRetry ? 'text-amber-400' : 'text-prime-muted'}`}>
                            <span className="opacity-50 inline-block w-16 shrink-0">{new Date(log.timestamp).toLocaleTimeString([], { hour12: false, second: '2-digit' })}</span>
                            <span className={AGENT_COLORS[log.agent] ? AGENT_COLORS[log.agent].split(' ')[0] : 'text-prime-text'}>
                                [{log.agent.replace('Agent', '')}]
                            </span>
                            <span className="text-prime-text/80 break-words line-clamp-2">
                                {log.action === 'retry' && <AlertTriangle size={12} className="inline mr-1 -mt-0.5" />}
                                {log.action === 'complete' && <CheckCircle2 size={12} className="inline mr-1 text-emerald-400 -mt-0.5" />}
                                {log.action}: {log.data ? JSON.stringify(log.data) : ''}
                            </span>
                        </div>
                    );
                })}
                {logs.length === 0 && (
                    <div className="text-prime-muted/50 text-center mt-10 italic">Awaiting AI Telemetry...</div>
                )}
            </div>
        </div>
    );
}
