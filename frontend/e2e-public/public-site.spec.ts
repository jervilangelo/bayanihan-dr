import { expect, test, type Page } from '@playwright/test'

/**
 * Checks the deployed GitHub Pages site (blueprint Phase 9): it must work on its own, under the repository
 * sub-path, with direct links and refreshes, and without contacting AWS or any other service.
 */

const PAGES = [
  { path: '', title: 'Overview' },
  { path: '#/backups', title: 'Backups' },
  { path: '#/recovery', title: 'Recovery' },
  { path: '#/activity', title: 'Activity' },
  { path: '#/settings', title: 'Settings' },
]

function watch(page: Page) {
  const site = new URL(test.info().project.use.baseURL as string)
  const issues: string[] = []
  page.on('request', (r) => {
    const u = new URL(r.url())
    if (u.protocol === 'data:') return
    if (u.hostname !== site.hostname) issues.push(`external request: ${r.url()}`)
    if (/amazonaws\.com|aws\.amazon\.com/.test(u.hostname)) issues.push(`AWS request: ${r.url()}`)
  })
  page.on('response', (r) => {
    if (r.status() >= 400) issues.push(`HTTP ${r.status()}: ${r.url()}`)
  })
  page.on('console', (m) => {
    if (m.type() === 'error') issues.push(`console error: ${m.text()}`)
  })
  page.on('pageerror', (e) => issues.push(`page error: ${e.message}`))
  return issues
}

for (const p of PAGES) {
  test(`${p.title}: direct link and refresh work under /bayanihan-dr/`, async ({ page }) => {
    const issues = watch(page)
    await page.goto(p.path)
    await expect(page.getByRole('heading', { level: 1, name: p.title })).toBeVisible()
    await page.reload()
    await expect(page.getByRole('heading', { level: 1, name: p.title })).toBeVisible()
    await expect(page).toHaveTitle(`${p.title} · BayanihanDR`)
    await expect(page.getByText(/Demo mode/).filter({ visible: true }).first()).toBeVisible()
    expect(issues).toEqual([])
  })
}

test('publishes the measured drill results with evidence links', async ({ page }) => {
  const issues = watch(page)
  await page.goto('')
  const panel = page.getByTestId('recorded-drills')
  await expect(panel.getByText('Recorded results, not simulated')).toBeVisible()
  await expect(panel.getByText('05:29', { exact: true })).toBeVisible()
  await expect(panel.getByRole('link', { name: /Evidence/ }).first()).toHaveAttribute('href', /docs\/evidence\/phase7-disaster-drill\.md$/)
  expect(issues).toEqual([])
})

test('the simulated recovery runs end to end with nothing but the static site', async ({ page }) => {
  const issues = watch(page)
  await page.goto('?simSpeed=1200#/recovery')
  await page.getByRole('checkbox', { name: /I understand this is a simulation/ }).check()
  await page.getByRole('button', { name: 'Review and approve' }).click()
  await page.getByRole('dialog', { name: 'Start the simulated recovery?' }).getByRole('button', { name: 'Approve and start' }).click()
  await expect(page.getByRole('heading', { name: 'Simulated recovery finished' })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText(/placeholders, not measurements/)).toBeVisible()
  expect(issues).toEqual([])
})

test('does not publish operational endpoints or secrets in the bundle', async ({ page, request }) => {
  await page.goto('')
  const scripts = await page.locator('script[src]').evaluateAll((els) => els.map((e) => (e as HTMLScriptElement).src))
  expect(scripts.length).toBeGreaterThan(0)
  for (const src of scripts) {
    const body = await (await request.get(src)).text()
    expect(body).not.toMatch(/__runner|runnerToken|admin-token|\b\d{12}\b.*amazonaws|AKIA[0-9A-Z]{16}/)
  }
})
