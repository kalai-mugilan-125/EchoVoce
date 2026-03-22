/**
 * Waveform.jsx
 * ─────────────
 * Animated waveform bars.
 * • active=true + speaking=false → listening (green pulse)
 * • speaking=true               → AI speaking (purple wave)
 * • active=false                → idle flat line
 */

import { useEffect, useRef } from 'react'

const BAR_COUNT = 28

export default function Waveform({ active, speaking }) {
  const barsRef = useRef([])

  useEffect(() => {
    let frame
    let t = 0

    const animate = () => {
      t += 0.06
      barsRef.current.forEach((bar, i) => {
        if (!bar) return
        let h
        if (!active && !speaking) {
          h = 3
        } else if (speaking) {
          // Smooth sine wave for AI speaking
          h = 10 + 22 * Math.abs(Math.sin(t + i * 0.4)) * Math.abs(Math.sin(t * 0.7 + i * 0.2))
        } else {
          // Jagged random-ish for listening
          h = 4 + 18 * Math.abs(Math.sin(t * 1.8 + i * 0.6)) * (0.4 + 0.6 * Math.random())
        }
        bar.style.height = `${h}px`
      })
      frame = requestAnimationFrame(animate)
    }

    animate()
    return () => cancelAnimationFrame(frame)
  }, [active, speaking])

  const color = speaking
    ? 'linear-gradient(180deg, #a78bfa, #667eea)'
    : active
    ? 'linear-gradient(180deg, #43e97b, #38f9d7)'
    : 'rgba(255,255,255,0.15)'

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '3px',
      height: '48px',
      padding: '0 4px',
    }}>
      {Array.from({ length: BAR_COUNT }).map((_, i) => (
        <div
          key={i}
          ref={el => barsRef.current[i] = el}
          style={{
            width: '3px',
            height: '3px',
            borderRadius: '2px',
            background: color,
            transition: 'height 0.08s ease, background 0.4s ease',
            flexShrink: 0,
          }}
        />
      ))}
    </div>
  )
}
