import { useState } from 'react'
import { Terminal, Copy, Check, ChevronDown, ChevronRight } from 'lucide-react'

function buildCLI(p) {
    const parts = ['python3 listing_generator/run.py']
    if (p.clientExcel) parts.push(`  --client "${p.clientExcel}"`)
    if (p.outputDir) parts.push(`  --output "${p.outputDir}"`)
    const m = p.mode || 'full'
    if (m === 'images_only') { parts.push('  --images-only'); parts.push('  --generate-images') }
    else if (m === 'search_terms_only') parts.push('  --search-terms-only')
    else if (m === 'full' && p.generateImages) parts.push('  --generate-images')
    if (p.generateImages && m !== 'search_terms_only') {
        const t = p.imageType
        if (t === 'main') parts.push('  --main-image-only')
        else if (t === 'lifestyle') parts.push('  --lifestyle-image-only')
        else if (t === 'why_choose_us') parts.push('  --why-choose-us-only')
        else if (t === 'banner') parts.push('  --banner-image-only')
    }
    if (p.browseNodes) parts.push(`  --browse-nodes "${p.browseNodes}"`)
    if (p.ingestKeywords) parts.push('  --ingest-keywords')
    if (p.analysisDir) parts.push(`  --analysis-dir "${p.analysisDir}"`)
    if (p.keywordIndex) parts.push(`  --keyword-index "${p.keywordIndex}"`)
    if (p.geminiModel) parts.push(`  --gemini-model ${p.geminiModel}`)
    if (p.skip > 0) parts.push(`  --skip ${p.skip}`)
    if (p.limit) parts.push(`  --limit ${p.limit}`)
    return parts.join(' \\\n')
}

export default function CLIPreview({ params }) {
    const [open, setOpen] = useState(false)
    const [copied, setCopied] = useState(false)
    const cmd = buildCLI(params)

    const copy = () => {
        navigator.clipboard.writeText(cmd)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
    }

    return (
        <div className="mt-6 border border-prime-border rounded-xl overflow-hidden bg-prime-surface shadow-sm">
            <button onClick={() => setOpen(!open)}
                className="w-full flex items-center justify-between px-4 py-3 bg-prime-bg hover:bg-prime-hover text-[12px] font-bold tracking-wide text-prime-muted hover:text-prime-text transition-colors !border-none !rounded-none outline-none group">
                <div className="flex items-center gap-2">
                    <Terminal size={14} className="text-prime-label group-hover:text-prime-accent transition-colors" />
                    CLI EQUIVALENT COMMAND
                </div>
                {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </button>

            {open && (
                <div className="relative bg-[#050505] border-t border-prime-divider pb-4 animate-in fade-in slide-in-from-top-2 duration-200">

                    {/* Header Bar */}
                    <div className="flex items-center justify-between px-4 py-2 border-b border-[#222] bg-[#111]">
                        <span className="text-[10px] text-prime-label font-mono">bash</span>
                        <button onClick={copy} title="Copy to clipboard"
                            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-medium transition-all
                      ${copied
                                    ? 'bg-prime-successBg text-prime-success border border-prime-success/30'
                                    : 'bg-prime-bg text-prime-muted border border-prime-divider hover:text-white hover:border-[#555]'}`}>
                            {copied ? <Check size={12} /> : <Copy size={12} />}
                            {copied ? 'COPIED' : 'COPY'}
                        </button>
                    </div>

                    {/* Terminal output */}
                    <pre className="font-mono text-[12px] text-prime-accent px-5 pt-4 whitespace-pre overflow-x-auto leading-relaxed custom-scrollbar">
                        <span className="text-prime-primary select-none mr-2">❯</span>{cmd}
                    </pre>
                </div>
            )}
        </div>
    )
}
