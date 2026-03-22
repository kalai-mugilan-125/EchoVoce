const BASE = ''  // proxied via vite to localhost:8000

export async function createSession() {
  const res = await fetch(`${BASE}/upload/session`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to create session')
  return res.json()
}

export async function uploadResume(sessionId, file) {
  const fd = new FormData()
  fd.append('session_id', sessionId)
  fd.append('file', file)
  const res = await fetch(`${BASE}/upload/resume`, { method: 'POST', body: fd })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Resume upload failed')
  }
  return res.json()
}

export async function uploadJD(sessionId, jobDescription) {
  const fd = new FormData()
  fd.append('session_id', sessionId)
  fd.append('job_description', jobDescription)
  const res = await fetch(`${BASE}/upload/jd`, { method: 'POST', body: fd })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'JD upload failed')
  }
  return res.json()
}

export async function getSessionStatus(sessionId) {
  const res = await fetch(`${BASE}/upload/status/${sessionId}`)
  if (!res.ok) throw new Error('Status fetch failed')
  return res.json()
}

export async function getHealth() {
  const res = await fetch(`${BASE}/health/system`)
  if (!res.ok) throw new Error('Health check failed')
  return res.json()
}
