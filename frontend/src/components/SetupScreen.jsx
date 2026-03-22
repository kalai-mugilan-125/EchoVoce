/**
 * SetupScreen.jsx
 * ───────────────
 * Step 1 of the app:
 *   • Upload resume (PDF/DOCX/TXT)
 *   • Paste job description
 *   • Choose interview style
 *   • Click "Start Interview"
 */

import { useState, useRef } from 'react'
import { createSession, uploadResume, uploadJD } from '../utils/api'

const STYLES = [
  { id: 'mixed',     label: 'Mixed',     desc: 'Balanced technical + behavioural' },
  { id: 'technical', label: 'Technical', desc: 'Deep dives into skills & systems'  },
  { id: 'hr',        label: 'HR Round',  desc: 'Soft skills, culture, career goals' },
]

export default function SetupScreen({ onReady }) {
  const [step, setStep]         = useState(1)  // 1=upload, 2=jd, 3=style
  const [resumeFile, setResumeFile] = useState(null)
  const [jdText, setJdText]     = useState('')
  const [style, setStyle]       = useState('mixed')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')
  const [uploadedResume, setUploadedResume] = useState(null)
  const fileRef = useRef(null)

  const handleFileDrop = (e) => {
    e.preventDefault()
    const file = e.dataTransfer?.files?.[0] || e.target.files?.[0]
    if (file) setResumeFile(file)
  }

  const handleStart = async () => {
    setLoading(true)
    setError('')
    try {
      // 1. Create session
      const { session_id } = await createSession()

      // 2. Upload resume (optional)
      if (resumeFile) {
        const result = await uploadResume(session_id, resumeFile)
        setUploadedResume(result)
      }

      // 3. Upload JD (optional)
      if (jdText.trim()) {
        await uploadJD(session_id, jdText.trim())
      }

      // 4. Hand off to interview room
      onReady({ sessionId: session_id, style })

    } catch (err) {
      setError(err.message || 'Setup failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
    }}>
      {/* Logo */}
      <div className="fade-up" style={{ textAlign: 'center', marginBottom: '40px' }}>
        <div style={{
          fontSize: '36px',
          fontWeight: 700,
          background: 'linear-gradient(135deg, #a78bfa, #67e8f9)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          letterSpacing: '-0.02em',
          marginBottom: '8px',
        }}>
          EchoVoce
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '15px' }}>
          AI-powered real-time voice interviewer
        </p>
      </div>

      {/* Card */}
      <div className="card fade-up" style={{ width: '100%', maxWidth: '520px', padding: '36px' }}>

        {/* Step indicator */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '32px' }}>
          {[1,2,3].map(s => (
            <div key={s} style={{
              flex: 1, height: '3px', borderRadius: '2px',
              background: s <= step
                ? 'linear-gradient(90deg, #667eea, #764ba2)'
                : 'var(--glass-border)',
              transition: 'background 0.3s',
            }} />
          ))}
        </div>

        {/* Step 1: Resume upload */}
        {step === 1 && (
          <div className="fade-up">
            <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '6px' }}>
              Upload your resume
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '24px' }}>
              PDF, DOCX, or TXT — the AI tailors every question to your background.
            </p>

            {/* Drop zone */}
            <div
              onClick={() => fileRef.current?.click()}
              onDrop={handleFileDrop}
              onDragOver={e => e.preventDefault()}
              style={{
                border: `2px dashed ${resumeFile ? 'rgba(102,126,234,0.6)' : 'var(--glass-border)'}`,
                borderRadius: 'var(--radius-md)',
                padding: '32px',
                textAlign: 'center',
                cursor: 'pointer',
                background: resumeFile ? 'rgba(102,126,234,0.08)' : 'transparent',
                transition: 'all 0.2s',
              }}
            >
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.docx,.doc,.txt"
                style={{ display: 'none' }}
                onChange={handleFileDrop}
              />
              <div style={{ fontSize: '32px', marginBottom: '12px' }}>
                {resumeFile ? '📄' : '⬆️'}
              </div>
              {resumeFile ? (
                <>
                  <div style={{ fontWeight: 500, marginBottom: '4px' }}>{resumeFile.name}</div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                    {(resumeFile.size / 1024).toFixed(0)} KB
                  </div>
                </>
              ) : (
                <>
                  <div style={{ fontWeight: 500, marginBottom: '4px' }}>Drop file here or click to browse</div>
                  <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>PDF · DOCX · TXT up to 10 MB</div>
                </>
              )}
            </div>

            <div style={{ display: 'flex', gap: '10px', marginTop: '24px' }}>
              <button className="btn-ghost" style={{ flex: 1 }} onClick={() => setStep(2)}>
                Skip
              </button>
              <button className="btn-primary" style={{ flex: 2 }} onClick={() => setStep(2)}>
                Continue →
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Job description */}
        {step === 2 && (
          <div className="fade-up">
            <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '6px' }}>
              Job description
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '24px' }}>
              Paste the role you're interviewing for. The AI will ask role-specific questions.
            </p>

            <label className="label">Job description</label>
            <textarea
              className="input"
              placeholder="e.g. We're looking for a backend engineer with 3+ years Python experience..."
              value={jdText}
              onChange={e => setJdText(e.target.value)}
              style={{ minHeight: '140px' }}
            />

            <div style={{ display: 'flex', gap: '10px', marginTop: '24px' }}>
              <button className="btn-ghost" style={{ flex: 1 }} onClick={() => setStep(1)}>
                ← Back
              </button>
              <button className="btn-ghost" style={{ flex: 1 }} onClick={() => setStep(3)}>
                Skip
              </button>
              <button className="btn-primary" style={{ flex: 2 }} onClick={() => setStep(3)}>
                Continue →
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Interview style */}
        {step === 3 && (
          <div className="fade-up">
            <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '6px' }}>
              Interview style
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '24px' }}>
              Choose how the AI interviewer should approach questions.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '28px' }}>
              {STYLES.map(s => (
                <div
                  key={s.id}
                  onClick={() => setStyle(s.id)}
                  style={{
                    padding: '14px 18px',
                    borderRadius: 'var(--radius-sm)',
                    border: `1px solid ${style === s.id ? 'rgba(102,126,234,0.7)' : 'var(--glass-border)'}`,
                    background: style === s.id ? 'rgba(102,126,234,0.12)' : 'var(--glass)',
                    cursor: 'pointer',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    transition: 'all 0.15s',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 500, fontSize: '14px' }}>{s.label}</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>{s.desc}</div>
                  </div>
                  {style === s.id && (
                    <div style={{
                      width: '18px', height: '18px', borderRadius: '50%',
                      background: 'var(--grad-btn)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: '11px', flexShrink: 0,
                    }}>✓</div>
                  )}
                </div>
              ))}
            </div>

            {error && (
              <div style={{
                padding: '12px 16px',
                borderRadius: 'var(--radius-sm)',
                background: 'rgba(245,87,108,0.12)',
                border: '1px solid rgba(245,87,108,0.3)',
                color: '#f5576c',
                fontSize: '13px',
                marginBottom: '16px',
              }}>
                {error}
              </div>
            )}

            <div style={{ display: 'flex', gap: '10px' }}>
              <button className="btn-ghost" style={{ flex: 1 }} onClick={() => setStep(2)}>
                ← Back
              </button>
              <button
                className="btn-primary"
                style={{ flex: 2 }}
                disabled={loading}
                onClick={handleStart}
              >
                {loading ? 'Starting...' : '🎙 Start Interview'}
              </button>
            </div>
          </div>
        )}
      </div>

      <p style={{ marginTop: '24px', fontSize: '12px', color: 'var(--text-muted)' }}>
        Runs fully locally · No data leaves your machine
      </p>
    </div>
  )
}
