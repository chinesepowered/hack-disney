import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

const backend = process.env.CAPY_BACKEND ?? 'http://localhost:8000'

export default defineConfig(({ mode }) => ({
  // `vite build --mode offline` -> one self-contained HTML file (fonts, art and JS inlined)
  plugins: mode === 'offline' ? [react(), viteSingleFile()] : [react()],
  build: mode === 'offline' ? { outDir: 'dist-offline', assetsInlineLimit: 100_000_000 } : {},
  server: {
    port: 5173,
    proxy: {
      '/api': backend,
      '/files': backend,
      '/ws': { target: backend.replace('http', 'ws'), ws: true },
    },
  },
}))
