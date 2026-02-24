import { useState } from 'react'
import { browseFiles } from '../api/client'
import { Folder, File, CornerLeftUp, X, Search } from 'lucide-react'

export default function FilePicker({ value, onChange, placeholder, ext, isDir = false }) {
    const [open, setOpen] = useState(false)
    const [dir, setDir] = useState('')
    const [items, setItems] = useState([])
    const [parent, setParent] = useState('')
    const [loading, setLoading] = useState(false)

    const load = async (path) => {
        setLoading(true)
        try {
            const data = await browseFiles(path, isDir ? '' : (ext || ''))
            setDir(data.directory); setParent(data.parent); setItems(data.items)
        } catch { }
        setLoading(false)
    }

    const openPicker = () => { setOpen(true); load(dir || value || '') }

    const select = (item) => {
        if (item.isDir && !isDir) { load(item.path) }
        else { onChange(item.path); setOpen(false) }
    }

    return (
        <div className="relative">
            <div className="flex focus-within:ring-1 focus-within:ring-white/10 rounded-md">
                <input
                    type="text"
                    value={value}
                    onChange={e => onChange(e.target.value)}
                    placeholder={placeholder}
                    className="rounded-r-none border-r-0 focus:ring-0 z-10 w-full"
                />
                <button type="button" onClick={openPicker}
                    className="shrink-0 bg-prime-surface border border-prime-border border-l-0 rounded-r-md text-prime-text px-4 hover:bg-[#222] hover:text-white transition-colors flex items-center gap-2 z-10 font-semibold text-[12px]">
                    <Search size={14} className="text-prime-muted" /> Browse
                </button>
            </div>

            {open && (
                <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4 animate-in fade-in duration-200" onClick={() => setOpen(false)}>
                    <div className="bg-[#111] border border-[#333] rounded-2xl w-full max-w-[600px] h-[60vh] flex flex-col overflow-hidden shadow-[0_30px_60px_rgba(0,0,0,0.8)] scale-100 transition-transform" onClick={e => e.stopPropagation()}>

                        {/* Modal Header */}
                        <div className="flex items-center justify-between px-5 py-4 border-b border-[#222] bg-[#161616] shrink-0">
                            <div className="flex flex-col">
                                <span className="text-[10px] uppercase tracking-widest text-prime-label font-bold mb-1">Select {isDir ? 'Directory' : 'File'}</span>
                                <span className="font-mono text-[13px] text-prime-text line-clamp-1 break-all bg-prime-bg px-2 py-0.5 rounded border border-prime-border">{dir || '/'}</span>
                            </div>
                            <button onClick={() => setOpen(false)} className="p-2 rounded-lg bg-transparent text-prime-muted hover:bg-[#222] hover:text-white transition-colors border-none group">
                                <X size={18} />
                            </button>
                        </div>

                        {/* File List */}
                        <div className="flex-1 overflow-y-auto p-3 custom-scrollbar bg-[#0A0A0A]">

                            {parent && (
                                <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer text-[13px] text-prime-muted hover:bg-[#1A1A1A] hover:text-white transition-colors mb-1"
                                    onClick={() => load(parent)}>
                                    <div className="w-8 h-8 rounded flex items-center justify-center bg-[#222]">
                                        <CornerLeftUp size={16} />
                                    </div>
                                    <span className="font-medium tracking-wide">Up to parent directory</span>
                                </div>
                            )}

                            {loading && (
                                <div className="flex flex-col items-center justify-center h-40 gap-3">
                                    <div className="w-6 h-6 rounded-full border-2 border-[#333] border-t-prime-primary animate-spin" />
                                    <span className="text-[12px] text-prime-muted">Scanning file system...</span>
                                </div>
                            )}

                            {!loading && items.length === 0 && (
                                <div className="flex flex-col items-center justify-center h-40 gap-3 text-prime-muted border border-dashed border-[#222] rounded-xl m-2 bg-[#111]">
                                    <Folder size={24} className="opacity-20" />
                                    <span className="text-[13px]">Folder is empty</span>
                                </div>
                            )}

                            {!loading && items.map(item => (
                                <div key={item.path}
                                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer text-[13px] hover:bg-prime-hover transition-colors group"
                                    onClick={() => select(item)}>
                                    <div className={`w-8 h-8 rounded flex items-center justify-center transition-colors
                    ${item.isDir ? 'bg-prime-primaryBg text-prime-primary group-hover:bg-prime-primary group-hover:text-white' : 'bg-prime-surface border border-prime-border text-prime-muted group-hover:text-prime-accent'}`}>
                                        {item.isDir ? <Folder size={16} fill="currentColor" fillOpacity={0.2} /> : <File size={16} />}
                                    </div>
                                    <span className={`flex-1 truncate tracking-wide ${item.isDir ? 'font-semibold text-prime-text' : 'font-medium text-prime-muted group-hover:text-white'}`}>{item.name}</span>
                                    {!item.isDir && item.size && <span className="text-[11px] text-prime-label font-mono shrink-0">{(item.size / 1024).toFixed(1)} KB</span>}
                                </div>
                            ))}
                        </div>

                        {/* Modal Footer */}
                        <div className="p-4 border-t border-[#222] bg-[#111] flex justify-end shrink-0">
                            {isDir && (
                                <button onClick={() => { onChange(dir); setOpen(false) }}
                                    className="bg-prime-accent text-black font-bold px-6 py-2 rounded-lg text-[13px] hover:bg-white hover:scale-[1.02] shadow-glow-subtle transition-all">
                                    Select Current Folder
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
