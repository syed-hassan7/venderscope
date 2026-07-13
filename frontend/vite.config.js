import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const hfApiProxy = {
  '/api': {
    target: 'https://darkitowo-venderscope-api.hf.space',
    changeOrigin: true,
    secure: true,
  },
}

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    proxy: mode === 'development' ? { '/api': 'http://127.0.0.1:8000' } : {}
  },
  preview: {
    proxy: hfApiProxy,
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom') || id.includes('node_modules/react-router-dom')) {
            return 'react-vendor'
          }
          if (id.includes('node_modules/axios')) return 'http'
        },
      },
    },
  },
}))

