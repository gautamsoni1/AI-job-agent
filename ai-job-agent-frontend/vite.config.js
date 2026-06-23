import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    chunkSizeWarningLimit: 800,
  },
  server: {
    // Must match FRONTEND_URL and CORS_ORIGINS in the backend .env so links
    // sent in verification/reset emails open this frontend.
    port: 3000,
    strictPort: true,
  },
})
