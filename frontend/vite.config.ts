/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig, type Plugin } from 'vite'

/**
 * Local operations mode (`npm run dev:ops`): serves the backup engine's status.json from <repo>/backups
 * (or BDR_STATUS_FILE). Dev server only (`apply: 'serve'`), so it never exists in the GitHub Pages build.
 * The dev server listens on localhost only.
 */
function localEngineStatus(): Plugin {
  const file = resolve(process.env.BDR_STATUS_FILE ?? resolve(__dirname, '../backups/status.json'))
  return {
    name: 'bdr-local-engine-status',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/bayanihan-dr/__local/status.json', (_req, res) => {
        res.setHeader('Cache-Control', 'no-store')
        res.setHeader('Content-Type', 'application/json')
        if (!existsSync(file)) {
          res.statusCode = 404
          res.end('{"error":"status.json not found"}')
          return
        }
        res.end(readFileSync(file))
      })
    },
  }
}

// GitHub Pages serves the site from /bayanihan-dr/ (blueprint §17).
export default defineConfig({
  base: '/bayanihan-dr/',
  plugins: [react(), tailwindcss(), localEngineStatus()],
  server: { port: 5173, strictPort: true },
  test: {
    include: ['src/**/*.test.ts'],
    environment: 'node',
  },
})
