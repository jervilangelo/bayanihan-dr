/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// GitHub Pages serves the site from /bayanihan-dr/ (blueprint §17).
export default defineConfig({
  base: '/bayanihan-dr/',
  plugins: [react(), tailwindcss()],
  server: { port: 5173, strictPort: true },
  test: {
    include: ['src/**/*.test.ts'],
    environment: 'node',
  },
})
