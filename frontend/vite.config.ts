import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  // maplibre-gl v6 loads its worker relative to its own module URL; pre-bundling breaks that.
  optimizeDeps: { exclude: ['maplibre-gl'] },
  build: {
    rolldownOptions: {
      output: {
        // Long-lived vendor chunks cache well across deploys of app code.
        codeSplitting: {
          groups: [
            { name: 'maplibre', test: /node_modules[\\/]maplibre-gl/ },
            { name: 'deckgl', test: /node_modules[\\/]@(deck|luma|loaders|math)\.gl/ },
          ],
        },
      },
    },
    // maplibre-gl and deck.gl are each ~1 MB minified and cannot be split further.
    chunkSizeWarningLimit: 1200,
  },
})
