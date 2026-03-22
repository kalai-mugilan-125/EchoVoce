/**
 * EndScreen.jsx
 * ─────────────
 * Shown after the interview ends.
 * Displays transcript summary and restart option.
 */

export default function EndScreen({ transcript, onRestart }) {
  const userCount = transcript.filter(m => m.role === 'user').length
  const aiCount   = transcript.filter(m => m.role === 'assistant').length

  const downloadTranscript = () => {
    const lines = transcript.map(m =>
      `[${m.role.toUpperCase()}] ${m.text}`
    ).join('\n\n')
    const blob = new Blob([lines], { type: 'text/plain' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = `interview-${Date.now()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '24px',
    }}>
      <div className="card fade-up" style={{ width: '100%', maxWidth: '560px', padding: '40px' }}>
        {/* Icon */}
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div style={{ fontSize: '48px', marginBottom: '12px' }}>🎉</div>
          <h2 style={{ fontSize: '22px', fontWeight: 700, marginBottom: '6px' }}>
            Interview Complete
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
            Great job! Here's a summary of your session.
          </p>
        </div>

        {/* Stats */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr',
          gap: '12px', marginBottom: '28px',
        }}>
          {[
            { label: 'Questions asked', value: aiCount },
            { label: 'Your responses',  value: userCount },
            { label: 'Total exchanges', value: transcript.length },
            { label: 'Status', value: 'Completed' },
          ].map(stat => (
            <div key={stat.label} style={{
              padding: '16px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--glass)',
              border: '1px solid var(--glass-border)',
              textAlign: 'center',
            }}>
              <div style={{ fontSize: '24px', fontWeight: 700,
                background: 'var(--grad-btn)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              }}>
                {stat.value}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                {stat.label}
              </div>
            </div>
          ))}
        </div>

        {/* Transcript preview */}
        {transcript.length > 0 && (
          <>
            <div className="divider" />
            <div style={{
              maxHeight: '200px', overflowY: 'auto',
              display: 'flex', flexDirection: 'column', gap: '8px',
              marginBottom: '24px',
            }}>
              {transcript.slice(-6).map((msg, i) => (
                <div key={i} style={{
                  fontSize: '13px',
                  color: msg.role === 'assistant' ? 'var(--text-secondary)' : 'var(--text-primary)',
                  lineHeight: 1.5,
                  paddingLeft: msg.role === 'user' ? '12px' : '0',
                  borderLeft: msg.role === 'user' ? '2px solid rgba(67,233,123,0.4)' : 'none',
                }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginRight: '6px' }}>
                    {msg.role === 'user' ? 'YOU' : 'AI'}
                  </span>
                  {msg.text}
                </div>
              ))}
            </div>
          </>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn-ghost" style={{ flex: 1 }} onClick={downloadTranscript}>
            Download Transcript
          </button>
          <button className="btn-primary" style={{ flex: 1 }} onClick={onRestart}>
            New Interview
          </button>
        </div>
      </div>
    </div>
  )
}
