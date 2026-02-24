import { useState, useCallback, useEffect } from 'react'
import { Tag, Zap, Image as ImageIcon, History, PanelLeft, Brain } from 'lucide-react'
import RunConfig from './components/RunConfig'
import LiveTerminal from './components/LiveTerminal'
import ProgressTracker from './components/ProgressTracker'
import OutputGallery from './components/OutputGallery'
import RunHistory from './components/RunHistory'
import AIVisualizer from './components/AIVisualizer'
import RLTraining from './components/RLTraining'
import './index.css'

export default function App() {
  const [activeTab, setActiveTab] = useState('run')
  const [job, setJob] = useState(null)
  const [progress, setProgress] = useState(null)
  const [jobStatus, setJobStatus] = useState(null)
  const [galleryRunId, setGalleryRunId] = useState(null)
  const [completedOutputDir, setCompletedOutputDir] = useState(null)
  const [isTerminalOpen, setIsTerminalOpen] = useState(true)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)

  const handleJobStarted = useCallback((jobId, outputDir) => {
    setJob({ jobId, outputDir })
    setJobStatus('running')
    setProgress(null)
    setActiveTab('run')
  }, [])

  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (jobStatus === 'running') {
        const msg = "A pipeline job is currently running. Are you sure you want to leave? This will not stop the backend process, but you will lose the live progress view."
        e.preventDefault()
        e.returnValue = msg
        return msg
      }
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [jobStatus])

  const handleProgress = useCallback((p) => setProgress(p), [])

  const handleDone = useCallback((data) => {
    setJobStatus(data.success ? 'done' : 'error')
    setCompletedOutputDir(data.outputDir || job?.outputDir)
  }, [job])

  const handleOpenGallery = useCallback((runId) => {
    setGalleryRunId(runId)
    setActiveTab('gallery')
  }, [])

  const tabs = [
    { id: 'run', icon: Zap, label: 'Run Pipeline' },
    { id: 'gallery', icon: ImageIcon, label: 'Gallery' },
    { id: 'history', icon: History, label: 'History' },
    { id: 'rl', icon: Brain, label: 'RL Training' },
  ]

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-prime-bg text-prime-text font-sans antialiased text-[13px]">
      {/* Header - Glassy Minimalist */}
      <header className="flex flex-col sm:flex-row items-center justify-between px-6 py-3 border-b border-prime-divider bg-prime-bg/80 backdrop-blur-md shrink-0 z-20">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="p-1.5 hover:bg-prime-hover rounded-md transition-colors text-prime-muted hover:text-prime-text"
            title="Toggle Sidebar"
          >
            <PanelLeft size={18} />
          </button>
          <div className="p-1.5 bg-prime-primary/10 rounded-lg border border-prime-primary/20 shadow-[0_0_15px_-3px_rgba(59,130,246,0.3)]">
            <Tag size={18} className="text-prime-primary" />
          </div>
          <div>
            <h1 className="font-semibold text-[15px] tracking-tight text-prime-text leading-none">Amazon Listing Generator</h1>
            <span className="text-[11px] text-prime-muted font-medium tracking-wide">INTERNAL TOOL</span>
          </div>
        </div>

        <nav className="flex items-center gap-1.5 mt-4 sm:mt-0 bg-prime-surface p-1 rounded-lg border border-prime-divider shadow-sm">
          {tabs.map(t => {
            const Icon = t.icon
            const isActive = activeTab === t.id
            return (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className={`px-3.5 py-1.5 rounded-md text-[13px] font-medium transition-all duration-300 flex items-center gap-2
                  ${isActive
                    ? 'bg-prime-hover text-prime-text shadow-sm ring-1 ring-white/5'
                    : 'bg-transparent text-prime-muted hover:text-prime-accent hover:bg-prime-hover/50'}`}
              >
                <Icon size={14} className={isActive ? "text-prime-primary" : "opacity-70"} />
                {t.label}
              </button>
            )
          })}
        </nav>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-hidden relative">
        {activeTab === 'run' && (
          <div className="flex h-full overflow-hidden">
            {/* Left Sidebar: Form */}
            <div className={`bg-prime-surface/50 border-r border-prime-divider overflow-y-auto z-10 custom-scrollbar transition-all duration-300 ease-in-out shrink-0 ${isSidebarOpen ? 'w-[380px] opacity-100' : 'w-0 opacity-0 overflow-hidden border-r-0'}`}>
              <div className="w-[380px]">
                <RunConfig
                  onJobStarted={handleJobStarted}
                  jobStatus={jobStatus}
                  jobId={job?.jobId}
                />
              </div>
            </div>

            {/* Right Pane: Logs & Progress */}
            <div className="flex flex-col flex-1 min-w-0 overflow-y-auto custom-scrollbar bg-prime-bg h-full transition-all duration-300">
              <ProgressTracker
                progress={progress}
                jobStatus={jobStatus}
                outputDir={completedOutputDir || job?.outputDir}
                onOpenGallery={() => handleOpenGallery(job?.jobId)}
              />
              <div className="flex-1 min-h-[350px] bg-prime-surface/30 flex flex-col">
                <AIVisualizer jobId={job?.jobId} />
              </div>
              <div className={`${isTerminalOpen ? 'h-64' : 'h-[50px]'} shrink-0 border-t border-prime-divider flex flex-col transition-all duration-300 ease-in-out`}>
                <LiveTerminal
                  jobId={job?.jobId}
                  onProgress={handleProgress}
                  onDone={handleDone}
                  isCollapsed={!isTerminalOpen}
                  onToggleCollapse={() => setIsTerminalOpen(!isTerminalOpen)}
                />
              </div>
            </div>
          </div>
        )}

        {/* Other Tabs */}
        <div className={`absolute inset-0 transition-opacity duration-300 ${activeTab === 'gallery' ? 'opacity-100 z-10' : 'opacity-0 pointer-events-none'}`}>
          <OutputGallery runId={galleryRunId} />
        </div>

        <div className={`absolute inset-0 bg-prime-bg transition-opacity duration-300 ${activeTab === 'history' ? 'opacity-100 z-10' : 'opacity-0 pointer-events-none'}`}>
          <RunHistory onOpenGallery={handleOpenGallery} />
        </div>

        <div className={`absolute inset-0 bg-prime-bg transition-opacity duration-300 ${activeTab === 'rl' ? 'opacity-100 z-10' : 'opacity-0 pointer-events-none'}`}>
          <RLTraining />
        </div>
      </main>
    </div>
  )
}
