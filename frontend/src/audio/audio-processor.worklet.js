/**
 * audio-processor.worklet.js
 * Audio worklet for real-time microphone processing
 * Replaces deprecated ScriptProcessorNode
 *
 * Bug 2 fix: accumulate 128-sample frames into 512-sample chunks before
 * posting to main thread — Silero VAD requires exactly 512 samples.
 */

const CHUNK_SIZE = 512  // must match VAD_CHUNK_SIZE in backend config

class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this._buffer = new Float32Array(CHUNK_SIZE)
    this._offset = 0
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0]
    if (!input || input.length === 0) return true

    const frame = input[0]  // 128 samples per call by default

    let frameOffset = 0
    while (frameOffset < frame.length) {
      const remaining = CHUNK_SIZE - this._offset
      const toCopy = Math.min(remaining, frame.length - frameOffset)

      this._buffer.set(frame.subarray(frameOffset, frameOffset + toCopy), this._offset)
      this._offset += toCopy
      frameOffset += toCopy

      if (this._offset === CHUNK_SIZE) {
        // Post a copy — buffer is reused next iteration
        this.port.postMessage({
          type: 'audiodata',
          data: this._buffer.slice(),
        })
        this._offset = 0
      }
    }

    return true // Keep the processor alive
  }
}

registerProcessor('audio-processor', AudioProcessor)
