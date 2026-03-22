import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/upload': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/ws': {
        target: 'https://localhost:8000',
        ws: true,
      },
    },
  },
  worker: {
    format: 'es',
  },
})
