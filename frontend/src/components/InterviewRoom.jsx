/**
 * InterviewRoom.jsx  (fixed)
 * ──────────────────────────
 * Fixes:
 *   • passes final transcript to onEnd() so EndScreen can display it
 *   • handles "listening" server event to re-enable mic after AI speaks
 *   • connect() called safely once even in React StrictMode
 */

import { useEffect, useRef } from 'react'
import { useInterview } from '../hooks/useInterview'
import Waveform from './Waveform'

const PHASE_LABEL = {
  connecting:  'Connecting...',
  ready:       'Ready',
  listening:   'Listening',
  processing:  'Thinking...',
  speaking:    'Speaking',
  ended:       'Interview ended',
  idle:        'Idle',
}

const PHASE_BADGE = {
  listening:  'badge-green',
  speaking:   'badge-purple',
  processing: 'badge-amber',
  connecting: 'badge-amber',
  ended:      'badge-red',
}

export default function InterviewRoom({ sessionId, style, onEnd }) {
  const {
    phase, transcript, aiSentence,
    isAISpeaking, isListening,
    silenceTimer, error,
    connect, disconnect,
  } = useInterview()

  const transcriptRef  = useRef(null)
  const didConnectRef  = useRef(false)

  // Connect exactly once — safe against StrictMode double-mount
  useEffect(() => {
    if (didConnectRef.current) return
    didConnectRef.current = true
    connect(sessionId, style)
    return () => disconnect()
  }, [])

  // Auto-scroll transcript
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight
    }
  }, [transcript])

  const handleEnd = () => {
    disconnect()
    onEnd(transcript)
  }

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      padding: '16px',
      gap: '12px',
      maxWidth: '900px',
      margin: '0 auto',
    }}>

      {/* ── Header ─────────────────────────────────── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 20px',
        borderRadius: 'var(--radius-md)',
        background: 'var(--glass)',
        border: '1px solid var(--glass-border)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{
            fontSize: '18px', fontWeight: 700,
            background: 'linear-gradient(135deg, #a78bfa, #67e8f9)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>EchoVoce</span>
          <span className={`badge ${PHASE_BADGE[phase] || 'badge-purple'}`}>
            <span className={`pulse-dot ${phase === 'speaking' ? '' : phase === 'ended' ? 'red' : ''}`} />
            {PHASE_LABEL[phase] || phase}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {transcript.filter(m => m.role === 'user').length} responses
          </span>
          <button
            className="btn-ghost"
            style={{ padding: '8px 16px', fontSize: '13px', color: '#f5576c', borderColor: 'rgba(245,87,108,0.3)' }}
            onClick={handleEnd}
          >
            End Interview
          </button>
        </div>
      </div>

      {/* ── Main area ──────────────────────────────── */}
      <div style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: '220px 1fr',
        gap: '12px',
        minHeight: 0,
      }}>

        {/* AI Panel */}
        <div className="card" style={{
          padding: '24px 20px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '20px',
        }}>
          {/* Avatar */}
          <div style={{
            width: '72px', height: '72px', borderRadius: '50%',
            background: isAISpeaking
              ? 'linear-gradient(135deg, #a78bfa, #667eea)'
              : 'linear-gradient(135deg, #302b63, #24243e)',
            border: `2px solid ${isAISpeaking ? 'rgba(167,139,250,0.6)' : 'var(--glass-border)'}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '28px',
            boxShadow: isAISpeaking ? '0 0 24px rgba(167,139,250,0.4)' : 'none',
            transition: 'all 0.4s',
          }}>
            🤖
          </div>

          <div style={{ textAlign: 'center' }}>
            <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: '4px' }}>AI Interviewer</div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'capitalize' }}>
              {style} round
            </div>
          </div>

          <Waveform active={isAISpeaking} speaking={isAISpeaking} />

          {aiSentence && (
            <div style={{
              fontSize: '12px',
              color: 'var(--text-secondary)',
              textAlign: 'center',
              lineHeight: 1.5,
              padding: '8px',
              background: 'rgba(102,126,234,0.08)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid rgba(102,126,234,0.15)',
            }}>
              "{aiSentence}"
            </div>
          )}

          {error && (
            <div style={{
              fontSize: '12px', color: '#f5576c',
              padding: '8px', borderRadius: 'var(--radius-sm)',
              background: 'rgba(245,87,108,0.1)',
              border: '1px solid rgba(245,87,108,0.2)',
              textAlign: 'center',
            }}>
              {error}
            </div>
          )}
        </div>

        {/* Transcript feed */}
        <div className="card" style={{
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
        }}>
          <div style={{
            fontSize: '12px', fontWeight: 500, color: 'var(--text-muted)',
            textTransform: 'uppercase', letterSpacing: '0.06em',
            marginBottom: '16px', flexShrink: 0,
          }}>
            Transcript
          </div>

          <div
            ref={transcriptRef}
            style={{
              flex: 1, overflowY: 'auto',
              display: 'flex', flexDirection: 'column', gap: '12px',
              paddingRight: '4px',
            }}
          >
            {transcript.length === 0 && (
              <div style={{
                flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'var(--text-muted)', fontSize: '14px', textAlign: 'center',
                lineHeight: 1.6,
              }}>
                {phase === 'connecting'
                  ? 'Connecting to backend...'
                  : 'Interview starting — the AI will greet you shortly.'}
              </div>
            )}

            {transcript.map((msg, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                  gap: '10px',
                  alignItems: 'flex-start',
                  animation: 'fadeUp 0.3s ease forwards',
                }}
              >
                <div style={{
                  width: '30px', height: '30px', borderRadius: '50%', flexShrink: 0,
                  background: msg.role === 'user'
                    ? 'linear-gradient(135deg, #43e97b, #38f9d7)'
                    : 'linear-gradient(135deg, #667eea, #764ba2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '14px',
                }}>
                  {msg.role === 'user' ? '🧑' : '🤖'}
                </div>

                <div style={{
                  maxWidth: '78%',
                  padding: '10px 14px',
                  borderRadius: msg.role === 'user' ? '16px 4px 16px 16px' : '4px 16px 16px 16px',
                  background: msg.role === 'user'
                    ? 'rgba(67,233,123,0.1)'
                    : 'rgba(102,126,234,0.1)',
                  border: `1px solid ${msg.role === 'user' ? 'rgba(67,233,123,0.2)' : 'rgba(102,126,234,0.2)'}`,
                  fontSize: '14px',
                  lineHeight: 1.6,
                  color: 'var(--text-primary)',
                }}>
                  {msg.text}
                </div>
              </div>
            ))}

            {phase === 'processing' && (
              <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                <div style={{
                  width: '30px', height: '30px', borderRadius: '50%',
                  background: 'linear-gradient(135deg, #667eea, #764ba2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px',
                }}>🤖</div>
                <div className="shimmer" style={{ width: '180px', height: '40px' }} />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Mic bar ─────────────────────────────────── */}
      <div style={{
        padding: '14px 24px',
        borderRadius: 'var(--radius-md)',
        background: 'var(--glass)',
        border: '1px solid var(--glass-border)',
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        flexShrink: 0,
      }}>
        <div style={{
          width: '40px', height: '40px', borderRadius: '50%', flexShrink: 0,
          background: isListening ? 'rgba(67,233,123,0.15)' : 'var(--glass)',
          border: `1px solid ${isListening ? 'rgba(67,233,123,0.4)' : 'var(--glass-border)'}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '18px', transition: 'all 0.3s',
        }}>
          {isListening ? '🎙' : '🔇'}
        </div>

        <Waveform active={isListening} speaking={false} />

        {silenceTimer > 0 && (
          <div style={{
            fontSize: '13px', color: 'var(--text-secondary)',
            display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0,
          }}>
            <div className="pulse-dot amber" />
            Sending in {silenceTimer}s
          </div>
        )}

        <div style={{ marginLeft: 'auto', fontSize: '12px', color: 'var(--text-muted)', flexShrink: 0 }}>
          {isListening
            ? 'Listening — speak naturally'
            : isAISpeaking
            ? 'AI speaking — interrupt anytime'
            : phase === 'processing'
            ? 'Processing your response...'
            : PHASE_LABEL[phase]}
        </div>
      </div>
    </div>
  )
}
