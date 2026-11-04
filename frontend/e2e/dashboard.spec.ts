import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const PAGES = [
  { path: '', title: 'Overview' },
  { path: '#/backups', title: 'Backups' },
  { path: '#/recovery', title: 'Recovery' },
  { path: '#/activity', title: 'Activity' },
  { path: '#/settings', title: 'Settings' },
]

/** Fail the test if the demo ever requests anything outside its own origin (no AWS, no APIs, no CDNs). */
function forbidExternalRequests(page: Page) {
  const external: string[] = []
  page.on('request', (r) => {
    const url = new URL(r.url())
    if (url.hostname !== 'localhost' && url.protocol !== 'data:') external.push(r.url())
  })
  return external
}

async function openMenuIfMobile(page: Page) {
  const menu = page.getByRole('button', { name: 'Open menu' })
  if (await menu.isVisible()) await menu.click()
}

test.describe('navigation', () => {
  for (const p of PAGES) {
    test(`direct link and refresh work for ${p.title}`, async ({ page }) => {
      const external = forbidExternalRequests(page)
      await page.goto(p.path)
      await expect(page.getByRole('heading', { level: 1, name: p.title })).toBeVisible()
      await page.reload()
      await expect(page.getByRole('heading', { level: 1, name: p.title })).toBeVisible()
      await expect(page).toHaveTitle(`${p.title} · BayanihanDR`)
      expect(external).toEqual([])
    })
  }

  test('the navigation reaches every page', async ({ page }) => {
    await page.goto('')
    for (const p of PAGES.slice(1)) {
      await openMenuIfMobile(page)
      await page.getByRole('navigation', { name: 'Pages' }).getByRole('link', { name: p.title }).filter({ visible: true }).click()
      await expect(page.getByRole('heading', { level: 1, name: p.title })).toBeVisible()
    }
  })

  test('an unknown address shows a not-found page inside the shell', async ({ page }) => {
    await page.goto('#/nowhere')
    await expect(page.getByRole('heading', { level: 1, name: 'Page not found' })).toBeVisible()
  })
})

test.describe('demo labelling', () => {
  for (const p of PAGES) {
    test(`${p.title} says the data is simulated`, async ({ page }) => {
      await page.goto(p.path)
      await expect(page.getByText(/Demo mode/).filter({ visible: true }).first()).toBeVisible()
    })
  }
})

test.describe('overview', () => {
  test('answers "are we protected?" with the newest verified point', async ({ page }) => {
    await page.goto('')
    await expect(page.getByText('47 min', { exact: true })).toBeVisible()
    await expect(page.getByText('Protected', { exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: /Plan a recovery/ })).toBeVisible()
  })
})

test.describe('backups', () => {
  test('filters problems and opens a manifest', async ({ page }) => {
    await page.goto('#/backups')
    await page.getByRole('tab', { name: /Problems/ }).click()
    await expect(page.getByText('4 of 4 shown')).toBeVisible()
    const first = page.getByRole('button', { expanded: false }).filter({ visible: true }).first()
    await first.click()
    await expect(page.getByText(/Checksum mismatch|power was out/).filter({ visible: true }).first()).toBeVisible()
  })

  test('"Recover to this point" pre-selects that point on the Recovery page', async ({ page }) => {
    await page.goto('#/backups')
    await page.getByRole('link', { name: 'Recover to this point' }).filter({ visible: true }).nth(2).click()
    await expect(page.getByRole('heading', { level: 1, name: 'Recovery' })).toBeVisible()
    await expect(page.getByRole('radio', { checked: true })).toHaveValue(/bk-20261104-03/)
  })
})

test.describe('simulated recovery', () => {
  test('runs end to end with explicit approval and records the result', async ({ page }) => {
    const external = forbidExternalRequests(page)
    await page.goto('?simSpeed=1200#/recovery')

    const approve = page.getByRole('button', { name: 'Review and approve' })
    await expect(approve).toBeDisabled()
    await page.getByRole('checkbox', { name: /I understand this is a simulation/ }).check()
    await expect(approve).toBeEnabled()
    await approve.click()

    const dialog = page.getByRole('dialog', { name: 'Start the simulated recovery?' })
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: 'Approve and start' }).click()

    await expect(page.getByRole('progressbar', { name: 'Simulated recovery progress' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Simulated recovery finished' })).toBeVisible({ timeout: 15_000 })
    await expect(page.getByRole('heading', { name: 'Result' })).toBeVisible()
    await expect(page.getByText(/placeholders, not measurements/)).toBeVisible()

    await page.getByRole('link', { name: 'View activity' }).click()
    await expect(page.getByText('Simulated recovery finished')).toBeVisible()
    await expect(page.getByText('Simulated recovery approved')).toBeVisible()
    expect(external).toEqual([])
  })

  test('a running simulation can be stopped, and approval cannot be re-opened meanwhile', async ({ page }) => {
    await page.goto('?simSpeed=20#/recovery')
    await page.getByRole('checkbox', { name: /I understand/ }).check()
    await page.getByRole('button', { name: 'Review and approve' }).click()
    await page.getByRole('button', { name: 'Approve and start' }).click()
    await expect(page.getByRole('heading', { name: 'Recovering (simulated)' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Review and approve' })).toHaveCount(0)

    // Leaving and coming back (in-app navigation) resumes the same job instead of offering a second one.
    for (const name of ['Overview', 'Recovery']) {
      await openMenuIfMobile(page)
      await page.getByRole('navigation', { name: 'Pages' }).getByRole('link', { name }).filter({ visible: true }).click()
      await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()
    }
    await expect(page.getByRole('button', { name: 'Review and approve' })).toHaveCount(0)
    await page.getByRole('button', { name: 'Stop simulation' }).click()
    await expect(page.getByRole('heading', { name: 'Simulation stopped' })).toBeVisible()
  })
})

test.describe('settings', () => {
  test('time-zone preference changes how times are shown and persists', async ({ page }) => {
    await page.goto('#/settings')
    await page.getByRole('radio', { name: 'UTC' }).check()
    await page.goto('#/backups')
    // 13:05 Philippine time is 05:05 UTC.
    await expect(page.getByText('Wed 4 Nov, 05:05').filter({ visible: true }).first()).toBeVisible()
    await page.reload()
    await expect(page.getByText('Wed 4 Nov, 05:05').filter({ visible: true }).first()).toBeVisible()
  })
})

test.describe('reduced motion', () => {
  test.use({ reducedMotion: 'reduce' })
  test('everything still renders and the simulation still completes', async ({ page }) => {
    await page.goto('?simSpeed=1200#/recovery')
    await page.getByRole('checkbox', { name: /I understand/ }).check()
    await page.getByRole('button', { name: 'Review and approve' }).click()
    await page.getByRole('button', { name: 'Approve and start' }).click()
    await expect(page.getByRole('heading', { name: 'Simulated recovery finished' })).toBeVisible({ timeout: 15_000 })
  })
})

test.describe('accessibility', () => {
  for (const p of PAGES) {
    test(`${p.title} has no serious or critical axe violations`, async ({ page }) => {
      await page.goto(p.path)
      await expect(page.getByRole('heading', { level: 1, name: p.title })).toBeVisible()
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(600) // let data and entrance motion settle
      const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
      const serious = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
      expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([])
    })
  }
})
