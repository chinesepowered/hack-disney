import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backend = process.env.CAPY_BACKEND ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': backend,
      '/files': backend,
      '/ws': { target: backend.replace('http', 'ws'), ws: true },
    },
  },
})
