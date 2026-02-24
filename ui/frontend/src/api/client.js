const API = 'http://localhost:8000'

export async function startRun(params) {
    const res = await fetch(`${API}/api/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
    })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
}

export async function stopRun(jobId) {
    const res = await fetch(`${API}/api/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jobId }),
    })
    return res.json()
}

export async function getRuns() {
    const res = await fetch(`${API}/api/runs`)
    return res.json()
}

export async function getRunDetail(runId) {
    const res = await fetch(`${API}/api/run/${runId}`)
    if (!res.ok) throw new Error('Run not found')
    return res.json()
}

export async function browseFiles(directory, ext = '') {
    const params = new URLSearchParams({ directory })
    if (ext) params.append('ext', ext)
    const res = await fetch(`${API}/api/files?${params}`)
    return res.json()
}

export function createWebSocket(jobId) {
    return new WebSocket(`ws://localhost:8000/ws/logs?jobId=${jobId}`)
}

export const WS_URL = (jobId) => `ws://localhost:8000/ws/logs?jobId=${jobId}`
