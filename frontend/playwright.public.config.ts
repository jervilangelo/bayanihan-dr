import { defineConfig, devices } from '@playwright/test'

// Tests the LIVE public site (GitHub Pages), not a local build. Override with PUBLIC_URL for a preview deployment.
const URL = process.env.PUBLIC_URL ?? 'https://jervilangelo.github.io/bayanihan-dr/'

export default defineConfig({
  testDir: './e2e-public',
  fullyParallel: true,
  retries: 1, // the network to GitHub Pages is not ours; one retry absorbs a transient blip
  reporter: [['list']],
  use: { baseURL: URL, trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
})
