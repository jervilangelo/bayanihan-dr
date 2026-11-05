import { defineConfig, devices } from '@playwright/test'

// Tests run against the PRODUCTION build served under the GitHub Pages base path.
// Override with E2E_PORT when 4174 is taken by another local project.
const PORT = Number(process.env.E2E_PORT ?? 4174)

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${PORT}/bayanihan-dr/`,
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: {
    command: `npm run build && npx vite preview --strictPort --port ${PORT}`,
    url: `http://localhost:${PORT}/bayanihan-dr/`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
