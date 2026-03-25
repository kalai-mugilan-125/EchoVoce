/**
 * useInterview.js  (fixed)
 * ─────────────────────────
 * Fixes applied:
 *   1. disconnect() guards readyState before send — no more InvalidStateError
 *   2. connect() ref-guards against React StrictMode double-invocation
 *   3. Cleanup on unmount uses ref so stale closure never fires on wrong WS
 *   4. Replaced ScriptProcessorNode with AudioWorkletNode
 */

import { useState, useRef, useCallback, useEffect } from 'react'
import audioWorkletUrl from '../audio/audio-processor.worklet.js?url'

const WS_URL = 'ws://localhost:8000/ws/interview'
const SAMPLE_RATE = 16000

export function useInterview() {
  const [phase, setPhase]               = useState('idle')
  const [transcript, setTranscript]     = useState([])
  const [aiSentence, setAiSentence]     = useState('')
  const [isAISpeaking, setIsAISpeaking] = useState(false)
  const [isListening, setIsListening]   = useState(false)
  const [silenceTimer, setSilenceTimer] = useState(0)
  const [error, setError]               = useState(null)
  const [sessionId, setSessionId]       = useState(null)

  const wsRef           = useRef(null)
  const mediaStreamRef  = useRef(null)
  const processorRef    = useRef(null)
  const audioCtxRef     = useRef(null)
  const audioQueueRef   = useRef([])
  const isPlayingRef    = useRef(false)
  const silenceRef      = useRef(null)
  const hasSpeechRef    = useRef(false)
  const connectedRef    = useRef(false)  // guards against StrictMode double-mount

  // ── Audio playback queue ──────────────────────────────
  const playNextChunk = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return
    isPlayingRef.current = true
    setIsAISpeaking(true)

    const blob  = audioQueueRef.current.shift()
    const url   = URL.createObjectURL(blob)
    const audio = new Audio(url)

    audio.onended = () => {
      URL.revokeObjectURL(url)
      isPlayingRef.current = false
      if (audioQueueRef.current.length > 0) {
        playNextChunk()
      } else {
        setIsAISpeaking(false)
        setPhase('listening')
        setIsListening(true)
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: 'tts_playback_done' }))
        }
      }
    }
    audio.onerror = () => {
      URL.revokeObjectURL(url)
      isPlayingRef.current = false
      setIsAISpeaking(false)
    }
    audio.play().catch(() => { isPlayingRef.current = false })
  }, [])

  const enqueueAudio = useCallback((wavBytes) => {
    const blob = new Blob([wavBytes], { type: 'audio/wav' })
    audioQueueRef.current.push(blob)
    playNextChunk()
  }, [playNextChunk])

  const stopAudioPlayback = useCallback(() => {
    audioQueueRef.current = []
    isPlayingRef.current  = false
    setIsAISpeaking(false)
  }, [])

  // ── Silence timer UI ──────────────────────────────────
  const startSilenceTimer = useCallback(() => {
    clearInterval(silenceRef.current)
    setSilenceTimer(5)
    let count = 5
    silenceRef.current = setInterval(() => {
      count -= 1
      setSilenceTimer(count)
      if (count <= 0) clearInterval(silenceRef.current)
    }, 1000)
  }, [])

  const resetSilenceTimer = useCallback(() => {
    clearInterval(silenceRef.current)
    setSilenceTimer(0)
  }, [])

  // ── WebSocket message handler ─────────────────────────
  const handleWSMessage = useCallback((event) => {
    // Binary → WAV audio
    if (event.data instanceof ArrayBuffer) {
      enqueueAudio(event.data)
      return
    }
    if (event.data instanceof Blob) {
      event.data.arrayBuffer().then(enqueueAudio)
      return
    }

    let msg
    try { msg = JSON.parse(event.data) } catch { return }

    switch (msg.type) {
      case 'ready':
        setSessionId(msg.session_id)
        setPhase('listening')
        setIsListening(true)
        break

      case 'transcript':
        if (msg.text) {
          setTranscript(prev => [...prev, { role: 'user', text: msg.text, ts: Date.now() }])
          resetSilenceTimer()
          hasSpeechRef.current = false
        }
        setPhase('processing')
        setIsListening(false)
        break

      case 'tts_start':
        setAiSentence(msg.sentence || '')
        setPhase('speaking')
        setTranscript(prev => {
          const last = prev[prev.length - 1]
          if (last?.role === 'assistant') {
            return [...prev.slice(0, -1), { ...last, text: last.text + ' ' + (msg.sentence || '') }]
          }
          return [...prev, { role: 'assistant', text: msg.sentence || '', ts: Date.now() }]
        })
        break

      case 'tts_end':
        setAiSentence('')
        break

      case 'listening':
        setPhase('listening')
        setIsListening(true)
        // Bug 4 fix: tell the mic handler a new turn started so the
        // silence countdown can fire again for this turn
        hasSpeechRef.current = false
        break

      case 'interrupt_ack':
        stopAudioPlayback()
        setPhase('listening')
        setIsListening(true)
        break

      case 'error':
        setError(msg.message || 'Unknown error')
        break

      case 'pong':
        break

      default:
        break
    }
  }, [enqueueAudio, resetSilenceTimer, stopAudioPlayback])

  // ── Microphone capture ────────────────────────────────
  const startMic = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: SAMPLE_RATE,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      })
      mediaStreamRef.current = stream

      const audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE })
      audioCtxRef.current = audioCtx

      // Load AudioWorklet and create processor
      await audioCtx.audioWorklet.addModule(audioWorkletUrl)
      const processor = new AudioWorkletNode(audioCtx, 'audio-processor')
      processorRef.current = processor

      let lastSpeechTime = Date.now()
      let silenceStarted = false

      // Handle messages from the worklet
      processor.port.onmessage = (event) => {
        if (event.data.type !== 'audiodata') return

        const ws = wsRef.current
        if (!ws || ws.readyState !== WebSocket.OPEN) return

        const float32 = event.data.data
        const rms     = Math.sqrt(float32.reduce((s, v) => s + v * v, 0) / float32.length)
        const hasSpeech = rms > 0.008

        if (hasSpeech) {
          lastSpeechTime       = Date.now()
          hasSpeechRef.current = true
          silenceStarted       = false
          resetSilenceTimer()

          // Bug 3 fix: interrupt AI if user starts speaking while TTS plays
          if (isPlayingRef.current) {
            stopAudioPlayback()
            ws.send(JSON.stringify({ type: 'interrupt' }))
          }
        } else {
          const silenceDur = (Date.now() - lastSpeechTime) / 1000
          if (silenceDur >= 1 && !silenceStarted && hasSpeechRef.current) {
            silenceStarted = true
            startSilenceTimer()
          }
        }

        // Bug 3 fix: do NOT send audio bytes while AI is speaking TTS.
        // The backend ignores them anyway, but sending wastes bandwidth and
        // can confuse the VAD silence timer on the next turn.
        if (isPlayingRef.current) return

        // float32 → int16 PCM → send
        const int16 = new Int16Array(float32.length)
        for (let i = 0; i < float32.length; i++) {
          int16[i] = Math.max(-32768, Math.min(32767, float32[i] * 32768))
        }
        ws.send(int16.buffer)
      }

      const source = audioCtx.createMediaStreamSource(stream)
      source.connect(processor)
      processor.connect(audioCtx.destination)

    } catch (err) {
      setError(`Microphone error: ${err.message}`)
    }
  }, [resetSilenceTimer, startSilenceTimer, stopAudioPlayback])

  const stopMic = useCallback(() => {
    processorRef.current?.disconnect()
    processorRef.current = null
    audioCtxRef.current?.close().catch(() => {})
    audioCtxRef.current = null
    mediaStreamRef.current?.getTracks().forEach(t => t.stop())
    mediaStreamRef.current = null
    resetSilenceTimer()
  }, [resetSilenceTimer])

  // ── Connect ───────────────────────────────────────────
  const connect = useCallback((sid, style = 'mixed') => {
    // Guard: React StrictMode mounts twice in dev — skip second mount
    if (connectedRef.current) return
    connectedRef.current = true

    setPhase('connecting')
    setError(null)

    const ws = new WebSocket(WS_URL)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'start', session_id: sid, style }))
      startMic()
    }

    ws.onmessage = handleWSMessage

    ws.onerror = () => setError('WebSocket connection failed. Is the backend running?')

    ws.onclose = () => {
      stopMic()
      setIsListening(false)
      setIsAISpeaking(false)
      connectedRef.current = false
    }
  }, [handleWSMessage, startMic, stopMic])

  // ── Disconnect ────────────────────────────────────────
  const disconnect = useCallback(() => {
    const ws = wsRef.current
    if (ws) {
      // Only send if socket is actually open — avoids InvalidStateError
      if (ws.readyState === WebSocket.OPEN) {
        try { ws.send(JSON.stringify({ type: 'end' })) } catch (_) {}
      }
      wsRef.current = null
    }
    stopMic()
    stopAudioPlayback()
    connectedRef.current = false
    setPhase('ended')
    setIsListening(false)
  }, [stopMic, stopAudioPlayback])

  // Keepalive ping every 20s
  useEffect(() => {
    const id = setInterval(() => {
      const ws = wsRef.current
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 20000)
    return () => clearInterval(id)
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearInterval(silenceRef.current)
      const ws = wsRef.current
      if (ws && ws.readyState === WebSocket.OPEN) {
        try { ws.send(JSON.stringify({ type: 'end' })) } catch (_) {}
        ws.close()
      }
      stopMic()
    }
  }, [stopMic])

  return {
    phase, transcript, aiSentence,
    isAISpeaking, isListening,
    silenceTimer, error, sessionId,
    connect, disconnect,
  }
}
