/**
 * audio-processor.worklet.js
 * Audio worklet for real-time microphone processing
 * Replaces deprecated ScriptProcessorNode
 */

class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.port.onmessage = (event) => {
      // Handle any messages from main thread if needed
    }
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0]
    if (input.length > 0) {
      const float32 = input[0]
      
      // Send audio data to main thread
      this.port.postMessage({
        type: 'audiodata',
        data: float32,
      })
    }
    
    return true // Keep the processor alive
  }
}

registerProcessor('audio-processor', AudioProcessor)
