import React, { useState, useEffect, useCallback } from 'react';
import {
    Brain, ThumbsUp, ThumbsDown, RefreshCw, CheckCircle2,
    XCircle, Database, Loader2, ChevronDown, ChevronUp, Tag, Cpu
} from 'lucide-react';

const API = 'http://localhost:8000';

function StatusPill({ text, type }) {
    const styles = {
        approved: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
        rejected: 'bg-red-500/10 text-red-400 border-red-500/20',
        pending: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    };
    return (
        <span className={`text-[10px] font-bold tracking-wider px-2 py-0.5 rounded-full border ${styles[type] || styles.pending}`}>
            {text}
        </span>
    );
}

function ProductCard({ product, runId, category, onRate }) {
    const [status, setStatus] = useState(null); // null | 'approved' | 'rejected' | 'loading'
    const [expanded, setExpanded] = useState(false);

    const handleRate = async (action) => {
        setStatus('loading');
        try {
            const res = await fetch(`${API}/api/feedback/rate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    asin: product.asin,
                    runId,
                    category: category || 'general',
                    action, // 'approve' | 'reject'
                }),
            });
            if (!res.ok) throw new Error(await res.text());
            setStatus(action === 'approve' ? 'approved' : 'rejected');
            onRate?.(product.asin, action);
        } catch (e) {
            console.error('Rating failed:', e);
            setStatus(null);
        }
    };

    const title = product.optimizedTitle || product.originalTitle || 'No title';
    const bullets = product.bullets || [];
    const searchTerms = product.searchTerms || '';

    return (
        <div className={`border rounded-xl overflow-hidden transition-all duration-300 ${status === 'approved' ? 'border-emerald-500/40 bg-emerald-500/5' :
            status === 'rejected' ? 'border-red-500/30 bg-red-500/5 opacity-60' :
                'border-prime-divider bg-prime-surface/40'
            }`}>

            {/* Card Header */}
            <div className="flex items-start gap-3 p-4">
                {/* ASIN badge */}
                <div className="shrink-0 mt-0.5 px-2 py-1 bg-prime-bg rounded-md border border-prime-divider">
                    <span className="text-[10px] font-mono text-prime-muted">{product.asin}</span>
                </div>

                {/* Title */}
                <div className="flex-1 min-w-0">
                    <p className="text-prime-text text-[13px] font-medium leading-snug line-clamp-2">{title}</p>
                    <div className="flex items-center gap-2 mt-1.5">
                        {product.productType && (
                            <span className="text-[10px] text-prime-muted bg-prime-bg px-1.5 py-0.5 rounded border border-prime-divider">
                                {product.productType}
                            </span>
                        )}
                        {product.brand && (
                            <span className="text-[10px] text-amber-400/70">{product.brand}</span>
                        )}
                        <span className="ml-auto text-[10px] text-prime-muted">{title.length} chars</span>
                    </div>
                </div>

                {/* Status or Action Buttons */}
                <div className="shrink-0 flex items-center gap-2">
                    {status === 'loading' && <Loader2 size={16} className="text-prime-muted animate-spin" />}
                    {status === 'approved' && <CheckCircle2 size={16} className="text-emerald-400" />}
                    {status === 'rejected' && <XCircle size={16} className="text-red-400" />}
                    {!status && (
                        <>
                            <button
                                onClick={() => handleRate('reject')}
                                className="p-1.5 rounded-lg border border-red-500/20 bg-red-500/5 text-red-400 hover:bg-red-500/15 hover:border-red-500/40 transition-all"
                                title="Reject — do not use as example"
                            >
                                <ThumbsDown size={14} />
                            </button>
                            <button
                                onClick={() => handleRate('approve')}
                                className="p-1.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5 text-emerald-400 hover:bg-emerald-500/15 hover:border-emerald-500/40 transition-all"
                                title="Approve — save to Neural Memory Vault"
                            >
                                <ThumbsUp size={14} />
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* Expandable Details */}
            <div className="border-t border-prime-divider">
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="w-full flex items-center justify-between px-4 py-2 text-[11px] text-prime-muted hover:text-prime-text hover:bg-prime-hover/30 transition-colors"
                >
                    <span>View Bullets & Search Terms</span>
                    {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
                {expanded && (
                    <div className="px-4 pb-4 space-y-3">
                        {/* Original vs Optimized */}
                        {product.originalTitle && product.optimizedTitle && product.originalTitle !== product.optimizedTitle && (
                            <div className="text-[11px]">
                                <p className="text-prime-muted mb-1 font-semibold tracking-wide">ORIGINAL TITLE</p>
                                <p className="text-prime-text/60 italic leading-snug">{product.originalTitle}</p>
                            </div>
                        )}
                        {/* Bullets */}
                        {bullets.length > 0 && (
                            <div className="text-[11px]">
                                <p className="text-prime-muted mb-1.5 font-semibold tracking-wide">BULLET POINTS</p>
                                <ul className="space-y-1">
                                    {bullets.map((b, i) => (
                                        <li key={i} className="flex gap-2 text-prime-text/80 leading-snug">
                                            <span className="text-prime-primary shrink-0">•</span>
                                            <span>{b}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                        {/* Search Terms */}
                        {searchTerms && (
                            <div className="text-[11px]">
                                <p className="text-prime-muted mb-1 font-semibold tracking-wide">SEARCH TERMS</p>
                                <p className="text-prime-text/70 font-mono leading-relaxed">{searchTerms}</p>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

export default function RLTraining() {
    const [runs, setRuns] = useState([]);
    const [selectedRun, setSelectedRun] = useState(null);
    const [products, setProducts] = useState([]);
    const [loading, setLoading] = useState(false);
    const [category, setCategory] = useState('');
    const [vaultStats, setVaultStats] = useState({ count: 0 });
    const [ratings, setRatings] = useState({}); // asin -> 'approved' | 'rejected'
    const [approveAllLoading, setApproveAllLoading] = useState(false);
    const [liveRunId, setLiveRunId] = useState(null); // tracks a currently-running job
    const [availableCategories, setAvailableCategories] = useState([]);
    const ratingsRef = React.useRef(ratings);
    ratingsRef.current = ratings;

    // ── Load available categories from keyword index ──────────────────────────
    useEffect(() => {
        fetch(`${API}/api/keyword-categories`)
            .then(r => r.json())
            .then(d => {
                const cats = d.categories || [];
                setAvailableCategories(cats);
                // Auto-select the first category so Approve All works out of the box
                if (cats.length > 0) setCategory(cats[0]);
            })
            .catch(() => { });
    }, []);

    // ── Fetch runs list; auto-select latest; detect live runs ────────────────
    const refreshRuns = useCallback(() => {
        fetch(`${API}/api/runs`).then(r => r.json()).then(data => {
            const all = data || [];
            const live = all.find(r => r.status === 'running');
            setLiveRunId(live ? live.id : null);

            const usable = all.filter(r =>
                r.status === 'done' || r.status === 'partial' ||
                r.status === 'running' || (r.successCount || 0) > 0
            );
            setRuns(usable);

            // Auto-select the latest run (running first, then most recent done)
            setSelectedRun(prev => {
                if (prev) return prev; // user already picked one — keep it
                if (live) return live.id;
                return usable.length > 0 ? usable[0].id : null;
            });
        }).catch(() => { });
    }, []);

    // ── Fetch products for the selected run; merge without wiping ratings ────
    const refreshProducts = useCallback((runId) => {
        if (!runId) return;
        fetch(`${API}/api/run/${runId}`)
            .then(r => r.json())
            .then(data => {
                setProducts(prev => {
                    const incoming = data.products || [];
                    // Only add products we don't already have (preserve rating state)
                    const existingAsins = new Set(prev.map(p => p.asin));
                    const newOnes = incoming.filter(p => !existingAsins.has(p.asin));
                    return newOnes.length > 0 ? [...prev, ...newOnes] : prev;
                });
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    // ── Initial load ─────────────────────────────────────────────────────────
    useEffect(() => { refreshRuns(); }, [refreshRuns]);

    // ── When selected run changes, reset and load fresh ──────────────────────
    useEffect(() => {
        if (!selectedRun) return;
        setLoading(true);
        setProducts([]);
        setRatings({});
        refreshProducts(selectedRun);
    }, [selectedRun, refreshProducts]);

    // ── Auto-poll every 5s when a live run is in progress ────────────────────
    useEffect(() => {
        if (!liveRunId) return;
        const interval = setInterval(() => {
            refreshRuns();
            if (selectedRun) refreshProducts(selectedRun);
        }, 30000);
        return () => clearInterval(interval);
    }, [liveRunId, selectedRun, refreshRuns, refreshProducts]);

    // ── Vault stats refresh after every approve ──────────────────────────────
    useEffect(() => {
        fetch(`${API}/api/feedback/stats`).then(r => r.json()).then(d => setVaultStats(d)).catch(() => { });
    }, [ratings]);

    const handleRate = useCallback((asin, action) => {
        setRatings(prev => ({ ...prev, [asin]: action }));
    }, []);

    const handleApproveAll = async () => {
        const unrated = products.filter(p => !ratings[p.asin]);
        if (unrated.length === 0) return;
        setApproveAllLoading(true);
        for (const p of unrated) {
            try {
                await fetch(`${API}/api/feedback/rate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        asin: p.asin, runId: selectedRun,
                        category: category || 'general', action: 'approve',
                    }),
                });
                setRatings(prev => ({ ...prev, [p.asin]: 'approved' }));
            } catch (e) { /* skip */ }
        }
        setApproveAllLoading(false);
    };

    const approvedCount = Object.values(ratings).filter(v => v === 'approved').length;
    const rejectedCount = Object.values(ratings).filter(v => v === 'rejected').length;


    return (
        <div className="flex h-full overflow-hidden bg-prime-bg">

            {/* Left sidebar — Runs */}
            <div className="w-64 shrink-0 border-r border-prime-divider bg-prime-surface/30 flex flex-col overflow-hidden">
                <div className="px-4 py-3 border-b border-prime-divider flex items-center gap-2">
                    <Brain size={15} className="text-prime-primary" />
                    <h2 className="text-[13px] font-semibold text-prime-text">Training Runs</h2>
                </div>
                {/* Vault Stats badge */}
                <div className="mx-3 mt-3 mb-1 p-2.5 rounded-lg border border-rose-500/20 bg-rose-500/5 flex items-center gap-2.5">
                    <Database size={13} className="text-rose-400 shrink-0" />
                    <div>
                        <p className="text-[10px] text-prime-muted leading-none">Neural Memory Vault</p>
                        <p className="text-[13px] font-bold text-rose-400 leading-snug">{vaultStats.count} examples</p>
                    </div>
                </div>
                <div className="flex-1 overflow-y-auto custom-scrollbar py-2">
                    {runs.length === 0 && (
                        <p className="text-prime-muted text-[11px] px-4 py-6 text-center">No completed runs yet</p>
                    )}
                    {runs.map(run => (
                        <button
                            key={run.id}
                            onClick={() => setSelectedRun(run.id)}
                            className={`w-full text-left px-4 py-2.5 border-l-2 transition-all ${selectedRun === run.id
                                ? 'border-prime-primary bg-prime-primary/5 text-prime-text'
                                : 'border-transparent text-prime-muted hover:text-prime-text hover:bg-prime-hover/30'
                                }`}
                        >
                            <div className="flex items-center gap-1.5">
                                <p className="text-[12px] font-medium truncate flex-1">{run.name}</p>
                                {run.id === liveRunId && (
                                    <span className="text-[9px] font-bold tracking-widest text-emerald-400 border border-emerald-500/30 bg-emerald-500/10 px-1 rounded animate-pulse shrink-0">LIVE</span>
                                )}
                            </div>
                            <p className="text-[10px] opacity-60 mt-0.5">{run.successCount || 0} products</p>
                        </button>
                    ))}
                </div>
            </div>

            {/* Main panel */}
            <div className="flex-1 flex flex-col overflow-hidden">

                {/* Toolbar */}
                <div className="shrink-0 px-5 py-3 border-b border-prime-divider bg-prime-surface/40 flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2 flex-1">
                        <Cpu size={14} className="text-prime-primary" />
                        <h3 className="text-[13px] font-semibold text-prime-text">RL Training Queue</h3>
                        {products.length > 0 && (
                            <span className="text-[10px] text-prime-muted bg-prime-bg border border-prime-divider px-2 py-0.5 rounded-full">
                                {products.length} products
                            </span>
                        )}
                    </div>

                    {/* Category Dropdown */}
                    <div className="flex items-center gap-2">
                        <Tag size={12} className="text-prime-muted shrink-0" />
                        <div className="relative">
                            <select
                                value={category}
                                onChange={e => setCategory(e.target.value)}
                                className="bg-prime-bg border border-prime-divider rounded-md pl-3 pr-7 py-1.5 text-[12px] text-prime-text focus:outline-none focus:border-prime-primary/50 w-44 transition-colors appearance-none cursor-pointer"
                            >
                                {availableCategories.length === 0 && (
                                    <option value="">⚠ No categories</option>
                                )}
                                {availableCategories.map(cat => (
                                    <option key={cat} value={cat}>{cat}</option>
                                ))}
                            </select>
                            <ChevronDown size={11} className="absolute right-2 top-1/2 -translate-y-1/2 text-prime-muted pointer-events-none" />
                        </div>
                    </div>

                    {/* Status pills */}
                    {approvedCount > 0 && <StatusPill text={`${approvedCount} Approved`} type="approved" />}
                    {rejectedCount > 0 && <StatusPill text={`${rejectedCount} Rejected`} type="rejected" />}

                    {/* Approve All */}
                    <button
                        onClick={handleApproveAll}
                        disabled={approveAllLoading || products.length === 0}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                        {approveAllLoading ? <Loader2 size={12} className="animate-spin" /> : <ThumbsUp size={12} />}
                        Approve All
                    </button>

                    {/* Refresh */}
                    <button
                        onClick={() => setSelectedRun(s => s)}
                        className="p-1.5 rounded-md border border-prime-divider text-prime-muted hover:text-prime-text hover:bg-prime-hover/30 transition-colors"
                    >
                        <RefreshCw size={13} />
                    </button>
                </div>

                {/* Category hint */}
                {!category && products.length > 0 && (
                    <div className="px-5 py-2 bg-amber-500/5 border-b border-amber-500/15 text-[11px] text-amber-400/80 flex items-center gap-2">
                        <span className="text-amber-400 font-bold">⚠</span>
                        Enter a <strong>Category</strong> above before approving. This tags which product type the memory belongs to.
                    </div>
                )}

                {/* Product Cards */}
                <div className="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-3">
                    {loading && (
                        <div className="flex items-center justify-center h-40">
                            <Loader2 size={20} className="text-prime-primary animate-spin" />
                        </div>
                    )}
                    {!loading && products.length === 0 && selectedRun && (
                        <div className="flex flex-col items-center justify-center h-40 text-prime-muted">
                            <Database size={28} className="mb-3 opacity-30" />
                            <p className="text-[13px]">No product data found for this run.</p>
                            <p className="text-[11px] mt-1 opacity-60">Make sure the run completed with analysis files.</p>
                        </div>
                    )}
                    {!loading && !selectedRun && (
                        <div className="flex flex-col items-center justify-center h-40 text-prime-muted">
                            <Brain size={28} className="mb-3 opacity-30" />
                            <p className="text-[13px]">Select a run from the left to start reviewing.</p>
                        </div>
                    )}
                    {!loading && products.map(product => (
                        <ProductCard
                            key={product.asin}
                            product={product}
                            runId={selectedRun}
                            category={category}
                            onRate={handleRate}
                        />
                    ))}
                </div>
            </div>
        </div>
    );
}
