import { useState } from 'react'
import { startRun, stopRun } from '../api/client'
import FilePicker from './FilePicker'
import CLIPreview from './CLIPreview'
import { Play, Square, Settings2, Image as ImageIcon, FileText, CheckCircle2, Type, ChevronDown, ChevronRight } from 'lucide-react'

const MODES = [
    { id: 'full', label: 'Full Pipeline', desc: 'Titles + Content + Images', icon: CheckCircle2 },
    { id: 'titles_content', label: 'Titles & Content Only', desc: 'Skip image generation', icon: Type },
    { id: 'images_only', label: 'Images Only', desc: 'Skip text generation', icon: ImageIcon },
    { id: 'search_terms_only', label: 'Keywords Only', desc: 'Only generate search terms', icon: FileText },
]

const IMAGE_TYPES = [
    { id: 'all', label: 'All Layouts' },
    { id: 'main', label: 'Main Product Only' },
    { id: 'lifestyle', label: 'Lifestyle Suite (×4)' },
    { id: 'why_choose_us', label: 'Why Choose Us Banner' },
    { id: 'banner', label: 'A+ Banner (1200×628)' },
]

export default function RunConfig({ onJobStarted, jobStatus, jobId }) {
    const [params, setParams] = useState({
        clientExcel: '', outputDir: '', mode: 'full', imageType: 'all',
        ingestKeywords: false, browseNodes: '', analysisDir: '',
        keywordIndex: '', geminiKey: '', geminiModel: '', skip: 0, limit: '',
        llmProvider: 'ollama', llmModel: '', llmBaseUrl: '', llmApiKey: '',
    })
    const [showAdvanced, setShowAdvanced] = useState(false)
    const [error, setError] = useState(null)
    const [starting, setStarting] = useState(false)

    const set = (k, v) => setParams(p => ({ ...p, [k]: v }))
    const isRunning = jobStatus === 'running'

    const handleRun = async () => {
        setError(null)
        if (!params.clientExcel) { setError('Client Excel is required'); return }
        setStarting(true)

        // Map the UI mode to the backend flags
        const runPayload = {
            ...params,
            generateImages: params.mode === 'full' || params.mode === 'images_only',
            limit: params.limit ? parseInt(params.limit) : null,
            skip: parseInt(params.skip) || 0,
        }

        try {
            const res = await startRun(runPayload)
            onJobStarted(res.jobId, res.outputDir)
        } catch (e) { setError(e.message) }
        setStarting(false)
    }

    const handleStop = async () => {
        if (jobId) await stopRun(jobId)
    }

    // Common Header Style
    const SectionHeader = ({ title }) => (
        <label className="text-[10px] font-bold text-prime-label uppercase tracking-widest mb-2.5 block flex items-center gap-2">
            {title}
            <div className="h-px bg-prime-divider flex-1 ml-1" />
        </label>
    )

    return (
        <div className="flex flex-col relative pb-20">
            {/* Primary Configuration */}
            <div className="p-6 pb-4 space-y-7 border-b border-prime-divider">

                {/* Core Inputs */}
                <div className="space-y-4">
                    <div>
                        <SectionHeader title="Source Data" />
                        <FilePicker value={params.clientExcel} onChange={v => set('clientExcel', v)} placeholder="Select client excel (.xlsx)" ext=".xlsx,.xls" />
                    </div>
                    <div>
                        <SectionHeader title="Output Destination" />
                        <FilePicker value={params.outputDir} onChange={v => set('outputDir', v)} placeholder="Defaults to 'output' folder" isDir />
                    </div>
                </div>

                {/* Mode Selector */}
                <div>
                    <SectionHeader title="Pipeline Mode" />
                    <div className="grid grid-cols-1 gap-2">
                        {MODES.map(m => {
                            const Icon = m.icon
                            const isSelected = params.mode === m.id
                            return (
                                <div key={m.id}
                                    className={`relative flex items-center p-3 rounded-lg cursor-pointer transition-all duration-200 border
                    ${isSelected
                                            ? 'bg-prime-primaryBg border-prime-primary/40 shadow-glow-primary'
                                            : 'bg-prime-surface border-prime-border hover:border-[#404040]'}`}
                                    onClick={() => set('mode', m.id)}>

                                    <div className={`flex items-center justify-center p-2 rounded-md mr-3 ${isSelected ? 'bg-prime-primary/20 text-prime-primary' : 'bg-prime-hover text-prime-muted'}`}>
                                        <Icon size={16} />
                                    </div>

                                    <div className="flex-1">
                                        <div className={`text-[13px] font-semibold tracking-wide ${isSelected ? 'text-prime-accent' : 'text-prime-text'}`}>{m.label}</div>
                                        <div className="text-[11px] text-prime-muted mt-0.5">{m.desc}</div>
                                    </div>

                                    {/* Custom Radio Button */}
                                    <div className={`w-4 h-4 rounded-full border flex items-center justify-center transition-colors ${isSelected ? 'border-prime-primary bg-prime-primary' : 'border-prime-label'}`}>
                                        {isSelected && <div className="w-1.5 h-1.5 bg-prime-bg rounded-full" />}
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>

                {/* Dynamic Image Options */}
                {(params.mode === 'full' || params.mode === 'images_only') && (
                    <div className="p-4 rounded-xl bg-prime-surface/50 border border-prime-divider space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
                        <div className="text-[11px] font-semibold text-prime-label uppercase tracking-widest flex items-center gap-2">
                            <ImageIcon size={14} className="text-prime-muted" /> Image Layout Settings
                        </div>
                        <div className="flex flex-col gap-1.5 pl-2">
                            {IMAGE_TYPES.map(t => (
                                <label key={t.id} onClick={() => set('imageType', t.id)} className="flex items-center gap-2.5 cursor-pointer group py-1">
                                    <div className={`w-3 h-3 rounded-full border transition-colors flex items-center justify-center
                    ${params.imageType === t.id ? 'border-prime-primary' : 'border-prime-label group-hover:border-prime-muted'}`}>
                                        {params.imageType === t.id && <div className="w-1.5 h-1.5 rounded-full bg-prime-primary shadow-glow-primary" />}
                                    </div>
                                    <span className={`text-[12px] transition-colors ${params.imageType === t.id ? 'text-prime-accent font-medium' : 'text-prime-muted group-hover:text-prime-text'}`}>
                                        {t.label}
                                    </span>
                                </label>
                            ))}
                        </div>
                    </div>
                )}

                {/* Range Selector */}
                <div>
                    <SectionHeader title="Processing Range" />
                    <div className="flex gap-4">
                        <div className="flex-1">
                            <label className="text-[11px] text-prime-label mb-1.5 block">Skip First N</label>
                            <input type="number" min={0} value={params.skip} onChange={e => set('skip', e.target.value)} className="w-full text-left font-mono" />
                        </div>
                        <div className="flex-1">
                            <label className="text-[11px] text-prime-label mb-1.5 block">Process Limit</label>
                            <input type="number" min={1} value={params.limit} onChange={e => set('limit', e.target.value)} placeholder="All" className="w-full text-left font-mono" />
                        </div>
                    </div>
                </div>

            </div>

            {/* Advanced Settings */}
            <div className="p-6 space-y-4 bg-prime-bg">
                <button onClick={() => setShowAdvanced(!showAdvanced)}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-prime-surface border border-prime-divider text-[12px] font-medium text-prime-muted hover:text-prime-accent hover:border-[#404040] transition-all">
                    <div className="flex items-center gap-2">
                        <Settings2 size={14} />
                        Advanced Configuration
                    </div>
                    {showAdvanced ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </button>

                {showAdvanced && (
                    <div className="space-y-4 p-4 rounded-xl border border-prime-divider bg-prime-surface/30 shadow-inner animate-in fade-in slide-in-from-top-2 duration-200">
                        <div>
                            <label className="text-[11px] text-prime-label mb-1.5 block">Browse Nodes Mapping Dir</label>
                            <FilePicker value={params.browseNodes} onChange={v => set('browseNodes', v)} isDir placeholder="/path/to/browse_nodes/" />
                        </div>
                        <div>
                            <label className="text-[11px] text-prime-label mb-1.5 block">Previous Analysis Dir (Cache)</label>
                            <FilePicker value={params.analysisDir} onChange={v => set('analysisDir', v)} isDir placeholder="Reuse existing analysis JSONs" />
                        </div>
                        <div>
                            <label className="text-[11px] text-prime-label mb-1.5 block">Keyword Search Index (.pkl)</label>
                            <FilePicker value={params.keywordIndex} onChange={v => set('keywordIndex', v)} placeholder="keyword_index.pkl" />
                        </div>
                        <label className="flex items-center justify-between cursor-pointer group mt-2">
                            <span className="text-[12px] text-prime-muted group-hover:text-prime-text transition-colors">Ingest New Keywords to DB</span>
                            <div className={`w-8 h-4.5 flex items-center rounded-full p-0.5 transition-colors ${params.ingestKeywords ? 'bg-prime-info shadow-glow-primary' : 'bg-prime-hover border border-prime-border'}`}>
                                <div className={`bg-white w-3.5 h-3.5 rounded-full shadow-md transform transition-transform ${params.ingestKeywords ? 'translate-x-[14px]' : 'translate-x-0'}`} />
                            </div>
                            <input type="checkbox" className="hidden" checked={params.ingestKeywords} onChange={e => set('ingestKeywords', e.target.checked)} />
                        </label>
                        <div className="h-px bg-prime-divider my-3" />
                        <div className="text-[11px] font-bold text-prime-label uppercase tracking-widest mb-1.5">Text Generation LLM</div>
                        <div>
                            <div className="flex gap-2 mb-3">
                                {['ollama', 'openai'].map(p => (
                                    <button key={p} onClick={() => set('llmProvider', p)}
                                        className={`flex-1 py-1.5 rounded-md text-[12px] font-medium border transition-colors ${params.llmProvider === p ? 'bg-prime-primary/20 border-prime-primary text-prime-primary shadow-glow-primary' : 'bg-prime-surface border-prime-divider text-prime-muted hover:border-[#404040]'}`}>
                                        {p === 'ollama' ? 'Local (Ollama)' : 'Cloud (OpenAI)'}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {params.llmProvider === 'openai' && (
                            <div>
                                <label className="text-[11px] text-prime-label mb-1.5 block">OpenAI API Key</label>
                                <input type="password" value={params.llmApiKey} onChange={e => set('llmApiKey', e.target.value)} placeholder="Will use OPENAI_API_KEY from .env" className="w-full font-mono text-[12px] p-2 rounded-md bg-prime-surface border border-prime-divider focus:border-prime-primary outline-none focus:shadow-glow-primary" />
                            </div>
                        )}

                        {params.llmProvider === 'ollama' && (
                            <div>
                                <label className="text-[11px] text-prime-label mb-1.5 block">Ollama Base URL</label>
                                <input type="text" value={params.llmBaseUrl} onChange={e => set('llmBaseUrl', e.target.value)} placeholder="http://localhost:11434" className="w-full font-mono text-[12px] p-2 rounded-md bg-prime-surface border border-prime-divider focus:border-prime-primary outline-none focus:shadow-glow-primary" />
                            </div>
                        )}

                        <div>
                            <label className="text-[11px] text-prime-label mb-1.5 block">Text Model Override</label>
                            <input type="text" value={params.llmModel} onChange={e => set('llmModel', e.target.value)} placeholder={params.llmProvider === 'ollama' ? "deepseek-v3.1:671b-cloud" : "gpt-4o"} className="w-full font-mono text-[12px] p-2 rounded-md bg-prime-surface border border-prime-divider focus:border-prime-primary outline-none focus:shadow-glow-primary" />
                        </div>

                        <div className="h-px bg-prime-divider my-3" />
                        <div className="text-[11px] font-bold text-prime-label uppercase tracking-widest mb-1.5">Vision / Image Generation LLM</div>
                        <div>
                            <label className="text-[11px] text-prime-label mb-1.5 block">Gemini API Key Override</label>
                            <input type="password" value={params.geminiKey} onChange={e => set('geminiKey', e.target.value)} placeholder="Uses GEMINI_API_KEY from .env" className="w-full font-mono text-[12px] p-2 rounded-md bg-prime-surface border border-prime-divider focus:border-prime-primary outline-none focus:shadow-glow-primary mb-3" />
                        </div>
                        <div>
                            <label className="text-[11px] text-prime-label mb-1.5 block">Gemini Model Identifier</label>
                            <input type="text" value={params.geminiModel} onChange={e => set('geminiModel', e.target.value)} placeholder="gemini-2.0-flash" className="w-full font-mono text-[12px] p-2 rounded-md bg-prime-surface border border-prime-divider focus:border-prime-primary outline-none focus:shadow-glow-primary" />
                        </div>
                    </div>
                )}

                {/* Error State */}
                {error && (
                    <div className="p-3 bg-prime-dangerBg border-l-2 border-prime-danger text-prime-danger text-[12px] rounded-r-md flex items-start gap-2 animate-in fade-in">
                        <div className="shrink-0 mt-0.5 rounded-full border border-prime-danger w-3 h-3 flex items-center justify-center leading-none text-[8px] font-bold">!</div>
                        {error}
                    </div>
                )}

                <CLIPreview params={{ ...params, generateImages: params.mode === 'full' || params.mode === 'images_only' }} />
            </div>

            {/* Sticky Action Footer */}
            <div className="absolute bottom-0 w-full p-4 bg-prime-surface/90 backdrop-blur-lg border-t border-prime-divider flex gap-3 z-10 shrink-0">
                <button onClick={handleRun} disabled={isRunning || starting}
                    className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-lg text-[13.5px] font-bold transition-all duration-300
                  ${isRunning || starting
                            ? 'bg-prime-hover text-prime-muted cursor-not-allowed'
                            : 'bg-prime-accent text-black hover:bg-white hover:shadow-glow-subtle hover:scale-[1.02]'}`}>
                    {starting ? (
                        <div className="w-4 h-4 rounded-full border-2 border-prime-muted border-t-white animate-spin" />
                    ) : (
                        <Play size={16} fill="currentColor" />
                    )}
                    {starting ? 'Initializing...' : 'Run Pipeline'}
                </button>

                <button onClick={handleStop} disabled={!isRunning}
                    className={`flex items-center justify-center gap-2 px-6 py-3 rounded-lg text-[13.5px] font-bold transition-all duration-300
                  ${!isRunning
                            ? 'bg-transparent text-prime-label border border-prime-divider cursor-not-allowed'
                            : 'bg-prime-dangerBg text-prime-danger border border-prime-danger hover:bg-prime-danger hover:text-white shadow-glow-danger hover:scale-[1.02]'}`}>
                    <Square size={14} fill={isRunning ? "currentColor" : "none"} />
                    Stop
                </button>
            </div>
        </div>
    )
}
