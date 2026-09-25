import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { port: 1420, host: '127.0.0.1' },
  build: {
    // Three.js is intentionally isolated in a vendor chunk. Its minified WebGL
    // runtime is larger than Vite's generic 500 kB warning threshold, but it
    // is cacheable independently from application code.
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-dom/client'],
          three: ['three', 'three/examples/jsm/loaders/GLTFLoader.js'],
        },
      },
    },
  },
})
