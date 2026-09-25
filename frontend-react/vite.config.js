import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [tailwindcss()],
  resolve: { dedupe: ['three', 'react', 'react-dom'] },
  server: { port: 5173, open: true },
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks: {
          three: ['three', '@react-three/fiber', '@react-three/drei', '@react-three/postprocessing'],
          charts: ['recharts'],
          motion: ['framer-motion'],
        },
      },
    },
  },
})
