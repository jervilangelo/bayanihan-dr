// Capture documentation screenshots of the public site (or another base URL).
// Usage (from frontend/): node scripts/screenshots.mjs [baseUrl] [outDir]
import { chromium, devices } from '@playwright/test'

const base = process.argv[2] ?? 'https://jervilangelo.github.io/bayanihan-dr/'
const out = process.argv[3] ?? '../docs/screenshots'

const shots = [
  { name: 'overview-desktop', path: '', viewport: { width: 1440, height: 900 }, fullPage: true },
  { name: 'backups-desktop', path: '#/backups', viewport: { width: 1440, height: 900 } },
  { name: 'recovery-desktop', path: '#/recovery', viewport: { width: 1440, height: 900 } },
  { name: 'activity-desktop', path: '#/activity', viewport: { width: 1440, height: 900 } },
  { name: 'overview-phone', path: '', device: 'Pixel 7' },
]

const browser = await chromium.launch()
for (const s of shots) {
  const context = await browser.newContext(s.device ? devices[s.device] : { viewport: s.viewport, deviceScaleFactor: 1 })
  const page = await context.newPage()
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto(base + s.path, { waitUntil: 'networkidle' })
  await page.getByRole('heading', { level: 1 }).waitFor()
  await page.waitForTimeout(600)
  await page.screenshot({ path: `${out}/${s.name}.png`, fullPage: Boolean(s.fullPage) })
  console.log(`saved ${out}/${s.name}.png`)
  await context.close()
}
await browser.close()
