import { useState, useEffect } from 'react'
import { Download, Search, ChevronDown, ChevronUp, Image as ImageIcon, MapPin, Tag, Box, Palette, Award, CheckCircle2 } from 'lucide-react'
import { getRunDetail } from '../api/client'

const API = 'http://localhost:8000'

const IMG_SLOTS = [
    { key: 'main_image', icon: Box, label: 'Main Product' },
    { key: 'lifestyle_1', icon: ImageIcon, label: 'Lifestyle 1' },
    { key: 'lifestyle_2', icon: ImageIcon, label: 'Lifestyle 2' },
    { key: 'lifestyle_3', icon: ImageIcon, label: 'Lifestyle 3' },
    { key: 'lifestyle_4', icon: ImageIcon, label: 'Lifestyle 4' },
    { key: 'why_choose_us', icon: Award, label: 'Why Choose Us' },
    { key: 'banner_image', icon: ImageIcon, label: 'A+ Banner' },
]

export default function OutputGallery({ runId }) {
    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [lightbox, setLightbox] = useState(null)
    const [search, setSearch] = useState('')

    useEffect(() => {
        if (!runId) return
        setLoading(true); setError(null); setData(null)
        getRunDetail(runId)
            .then(setData)
            .catch(e => setError(e.message || 'Failed to load'))
            .finally(() => setLoading(false))
    }, [runId])

    if (!runId) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-prime-muted gap-4 p-10 font-sans">
                <div className="w-16 h-16 rounded-2xl bg-prime-surface border border-prime-border flex items-center justify-center shadow-lg">
                    <ImageIcon size={28} className="text-prime-label" />
                </div>
                <p className="text-[14px]">Select <strong className="text-prime-text">Open</strong> on a run from History to view generated assets.</p>
            </div>
        )
    }

    if (loading) return (
        <div className="flex flex-col items-center justify-center h-full gap-3">
            <div className="w-6 h-6 rounded-full border-2 border-prime-muted border-t-prime-primary animate-spin" />
            <span className="text-[13px] text-prime-muted font-medium">Loading gallery data...</span>
        </div>
    )
    if (error) return <div className="flex items-center justify-center h-full text-prime-danger text-[13px] font-medium">Failed: {error}</div>
    if (!data) return null

    const products = (data.products || []).filter(p =>
        !search || [p.asin, p.optimizedTitle, p.originalTitle, p.brand]
            .some(v => v?.toLowerCase().includes(search.toLowerCase()))
    )

    return (
        <div className="flex flex-col h-full overflow-hidden bg-prime-bg">

            {/* Glassy Toolbar */}
            <div className="flex items-center gap-4 px-6 py-4 bg-prime-surface/80 backdrop-blur-md border-b border-prime-divider shrink-0 flex-wrap z-10 sticky top-0">

                <div className="flex flex-col">
                    <span className="text-[10px] font-bold text-prime-label uppercase tracking-widest mb-0.5">Current Run</span>
                    <div className="flex items-center gap-2.5">
                        <span className="font-semibold text-[15px] tracking-tight">{data.runName || runId}</span>
                        <span className="badge bg-prime-bg border-prime-border text-prime-muted">{data.products?.length} items</span>
                    </div>
                </div>

                {/* Global Search */}
                <div className="flex-1 max-w-[400px] relative ml-4">
                    <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-prime-label" />
                    <input
                        className="pl-9 !bg-prime-bg !border-prime-divider !text-[13px] focus:!border-[#404040] focus:!ring-white/5 transition-all w-full"
                        type="text"
                        placeholder="Search ASIN, title, brand..."
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                    />
                </div>

                {data.excelPath && (
                    <a className="ml-auto flex items-center gap-2 bg-prime-successBg text-prime-success border border-prime-success/30 px-4 py-2 rounded-lg text-[13px] font-semibold hover:bg-prime-success hover:text-white transition-all shadow-glow-success"
                        href={`${API}${data.excelPath}`} download>
                        <Download size={14} />
                        Export Excel
                    </a>
                )}
            </div>

            {products.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-prime-muted mt-10">
                    <Search size={32} className="mb-3 opacity-20" />
                    No products match "{search}"
                </div>
            )}

            {/* Product Grid Layout */}
            <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 custom-scrollbar scroll-smooth">
                {products.map(p => (
                    <ProductCard key={p.asin} product={p} onImageClick={setLightbox} />
                ))}
            </div>

            {/* Elegant Lightbox */}
            {lightbox && (
                <div className="fixed inset-0 bg-black/95 backdrop-blur-sm z-[999] flex items-center justify-center p-6 transition-opacity" onClick={() => setLightbox(null)}>
                    <div className="bg-[#0A0A0A] border border-prime-divider rounded-2xl max-w-[95vw] max-h-[95vh] overflow-hidden flex flex-col shadow-[0_0_50px_rgba(0,0,0,0.5)] transform scale-100 transition-transform" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between px-5 py-3 border-b border-[#222] bg-[#111] shrink-0">
                            <span className="font-semibold text-[14px] text-prime-accent">{lightbox.label}</span>
                            <div className="flex gap-3 items-center">
                                <a href={lightbox.src} download className="flex items-center gap-1.5 bg-[#222] border border-[#333] text-prime-accent px-3 py-1.5 rounded-md text-[12px] hover:border-prime-primary hover:text-prime-primary transition-all">
                                    <Download size={12} /> Save
                                </a>
                                <button onClick={() => setLightbox(null)} className="p-1.5 rounded bg-transparent text-prime-muted hover:bg-[#222] hover:text-prime-text transition-colors border-none group">
                                    ✕
                                </button>
                            </div>
                        </div>
                        <div className="p-4 flex items-center justify-center flex-1 min-h-0 bg-black/50">
                            <img src={lightbox.src} alt={lightbox.label} className="max-w-full max-h-[calc(90vh-80px)] object-contain block drop-shadow-2xl rounded" />
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

function ProductCard({ product, onImageClick }) {
    const [expanded, setExpanded] = useState(false)
    const images = product.images || {}
    const imageSlots = IMG_SLOTS.filter(s => images[s.key])
    const origLen = product.originalTitle?.length || 0
    const optLen = product.optimizedTitle?.length || 0
    const gain = optLen - origLen
    const hasDetails = product.keyFeatures?.length > 0 || product.usage || product.targetAudience

    return (
        <div className="panel-card flex flex-col overflow-hidden transition-all duration-300 hover:border-[#404040] group shrink-0">

            {/* High-density Header */}
            <div className="flex items-center justify-between px-5 py-3.5 bg-prime-surface border-b border-prime-divider">
                <div className="flex flex-wrap items-center gap-2">
                    <div className="bg-prime-primary/10 text-prime-primary border border-prime-primary/20 px-2 py-0.5 rounded font-mono text-[13px] font-bold tracking-wider mr-2">{product.asin}</div>

                    {/* Metadata Badges using Lucide Icons */}
                    {product.brand && <span className="flex items-center gap-1.5 badge text-prime-muted border-prime-divider bg-prime-bg"><Tag size={10} /> {product.brand}</span>}
                    {product.country && <span className="flex items-center gap-1.5 badge text-prime-muted border-prime-divider bg-prime-bg"><MapPin size={10} /> {product.country}</span>}
                    {product.size && <span className="flex items-center gap-1.5 badge text-prime-muted border-prime-divider bg-prime-bg"><Box size={10} /> {product.size}</span>}
                    {product.laCategory && <span className="flex items-center gap-1.5 badge text-prime-muted border-prime-divider bg-prime-bg">{product.laCategory}</span>}
                    {product.colors?.length > 0 && <span className="flex items-center gap-1.5 badge text-prime-muted border-prime-divider bg-prime-bg"><Palette size={10} /> {product.colors[0]}</span>}
                </div>

                <div className="flex items-center gap-1.5 text-[11px] font-bold tracking-wider uppercase text-prime-success bg-prime-successBg px-2.5 py-1 rounded-md border border-prime-success/20">
                    <CheckCircle2 size={12} /> Processed
                </div>
            </div>

            {/* Copywriting Section */}
            {(product.originalTitle || product.optimizedTitle) ? (
                <div className="flex flex-col md:flex-row divide-y md:divide-y-0 md:divide-x divide-prime-divider bg-prime-bg shrink-0">

                    {/* BEFORE Title */}
                    {product.originalTitle && (
                        <div className="flex-1 p-5 space-y-2 opacity-80 group-hover:opacity-100 transition-opacity">
                            <div className="flex items-center justify-between">
                                <span className="text-[10px] font-bold uppercase tracking-widest text-[#F59E0B] flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-[#F59E0B]" /> Original Copy</span>
                                <span className="text-[11px] text-prime-label">{origLen} chars</span>
                            </div>
                            <p className="text-[13px] leading-relaxed text-prime-muted line-clamp-3" title={product.originalTitle}>
                                {product.originalTitle}
                            </p>
                        </div>
                    )}

                    {/* AFTER Title (Optimized) */}
                    {product.optimizedTitle && (
                        <div className="flex-[1.5] p-5 space-y-2 bg-prime-successBg/10">
                            <div className="flex flex-wrap items-center justify-between gap-4">
                                <span className="text-[10px] font-bold uppercase tracking-widest text-prime-success flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-prime-success shadow-glow-success" /> Optimized Copy</span>
                                <span className="text-[11px] text-prime-success font-medium bg-prime-success/10 px-2 py-0.5 rounded">
                                    {optLen} chars {gain > 0 && <strong className="ml-1 tracking-wider">+{gain}</strong>}
                                </span>
                            </div>
                            <p className="text-[14px] leading-relaxed text-prime-text font-medium" title={product.optimizedTitle}>
                                {product.optimizedTitle}
                            </p>
                        </div>
                    )}
                </div>
            ) : (
                <div className="px-5 py-3 border-b border-prime-divider text-[12px] text-prime-label italic bg-prime-bg shrink-0">Copywriting module skipped</div>
            )}

            {/* Visual Assets Grid */}
            {imageSlots.length > 0 ? (
                <div className="p-5 border-t border-prime-divider bg-prime-surface shrink-0">
                    <div className="text-[10px] font-bold text-prime-label uppercase tracking-widest mb-3">Generated Assets</div>
                    <div className="flex flex-wrap gap-4">
                        {imageSlots.map(({ key, icon: Icon, label }) => {
                            const fullSrc = `${API}${images[key]}`
                            return (
                                <div key={key}
                                    className="cursor-pointer group/img flex flex-col gap-2"
                                    onClick={() => onImageClick({ src: fullSrc, label })}>
                                    <div className="w-[120px] h-[120px] rounded-xl overflow-hidden border border-prime-border relative bg-prime-input before:absolute before:inset-0 before:bg-prime-primary/0 hover:before:bg-prime-primary/20 before:transition-colors">
                                        <img src={fullSrc} alt={label} loading="lazy" className="w-full h-full object-cover transition-transform duration-500 group-hover/img:scale-110" />
                                    </div>
                                    <div className="flex flex-col items-center">
                                        <span className="text-[11px] text-prime-muted font-medium flex items-center gap-1 transition-colors group-hover/img:text-prime-accent">
                                            <Icon size={10} /> {label}
                                        </span>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            ) : (
                <div className="px-5 py-3 border-t border-prime-divider text-[12px] text-prime-label italic bg-prime-surface shrink-0">Visuals module skipped</div>
            )}

            {/* Details Accordion */}
            {hasDetails && (
                <div className="border-t border-prime-divider shrink-0">
                    <button
                        onClick={() => setExpanded(!expanded)}
                        className="w-full flex items-center justify-between px-5 py-3 bg-prime-surface text-[12px] font-medium text-prime-muted hover:bg-prime-hover hover:text-prime-text transition-colors outline-none !border-none !rounded-none"
                    >
                        <span>Marketing AI & Analysis Metadata</span>
                        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>

                    {expanded && (
                        <div className="px-5 py-5 border-t border-prime-divider bg-prime-bg grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-in fade-in slide-in-from-top-2 duration-300">

                            {product.keyFeatures?.length > 0 && (
                                <div className="col-span-full mb-2">
                                    <h4 className="text-[10px] font-bold text-prime-label uppercase tracking-widest mb-2.5 flex items-center gap-1.5"><Tag size={12} /> Key Extracted Features</h4>
                                    <div className="flex flex-wrap gap-2">
                                        {product.keyFeatures.map((f, i) => (
                                            <span key={i} className="px-2.5 py-1 rounded bg-[#161616] border border-[#222] text-[12px] text-prime-muted">{f}</span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {product.usage && (
                                <div>
                                    <h4 className="text-[10px] font-bold text-prime-label uppercase tracking-widest mb-2 flex items-center gap-1.5"><Box size={12} /> Usage Context</h4>
                                    <p className="text-[13px] leading-relaxed text-[#A1A1AA]">{product.usage}</p>
                                </div>
                            )}

                            {product.targetAudience && (
                                <div>
                                    <h4 className="text-[10px] font-bold text-prime-label uppercase tracking-widest mb-2 flex items-center gap-1.5"><PinIcon /> Target Demographics</h4>
                                    <p className="text-[13px] leading-relaxed text-[#A1A1AA]">{product.targetAudience}</p>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

// Inline fallback for Pin if map-pin is missing
function PinIcon() {
    return <MapPin size={12} />
}
