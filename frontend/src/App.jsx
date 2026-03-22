/**
 * App.jsx
 * ───────
 * Top-level screen router.
 *
 * Screens:
 *   setup → interview → end → setup
 */

import { useState } from 'react'
import SetupScreen    from './components/SetupScreen'
import InterviewRoom  from './components/InterviewRoom'
import EndScreen      from './components/EndScreen'

export default function App() {
  const [screen, setScreen]         = useState('setup')
  const [sessionData, setSessionData] = useState(null)
  const [transcript, setTranscript]   = useState([])

  const handleReady = ({ sessionId, style }) => {
    setSessionData({ sessionId, style })
    setTranscript([])
    setScreen('interview')
  }

  const handleEnd = (finalTranscript = []) => {
    setTranscript(finalTranscript)
    setScreen('end')
  }

  const handleRestart = () => {
    setSessionData(null)
    setTranscript([])
    setScreen('setup')
  }

  return (
    <>
      {screen === 'setup' && (
        <SetupScreen onReady={handleReady} />
      )}

      {screen === 'interview' && sessionData && (
        <InterviewRoom
          sessionId={sessionData.sessionId}
          style={sessionData.style}
          onEnd={handleEnd}
        />
      )}

      {screen === 'end' && (
        <EndScreen
          transcript={transcript}
          onRestart={handleRestart}
        />
      )}
    </>
  )
}
