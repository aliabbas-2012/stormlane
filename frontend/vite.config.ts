import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Dev requests stay same-origin through this proxy, so CORS never depends on which port
  // Vite picked. Production calls VITE_API_BASE_URL directly.
  server: { proxy: { '/api': 'http://localhost:8000' } },
  // maplibre-gl alone is ~800 kB minified; the default 500 kB warning is just noise here.
  build: { chunkSizeWarningLimit: 1200 },
})
