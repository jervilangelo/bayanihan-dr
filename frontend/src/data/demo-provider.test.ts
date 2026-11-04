import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createDemoProvider } from './demo-provider'
import { TOTAL_SIMULATED_SECONDS } from './simulation'

let realNow = 0
const clock = () => realNow
const provider = () => createDemoProvider({ now: clock, latencyMs: 0, speed: 100 })

beforeEach(() => {
  realNow = 0
  // The demo must never reach the network: AWS, Terraform or any backend.
  vi.stubGlobal('fetch', () => {
    throw new Error('network access is forbidden in demo mode')
  })
})
afterEach(() => vi.unstubAllGlobals())

describe('demo provider', () => {
  it('identifies itself as demo mode', () => {
    expect(provider().mode).toBe('demo')
  })

  it('serves every read without network access', async () => {
    const p = provider()
    const [overview, backups, activity, settings] = await Promise.all([
      p.getOverview(), p.listBackups(), p.listActivity(), p.getSettings(),
    ])
    expect(overview.readiness.state).toBe('protected')
    expect(overview.primary.status).toBe('online')
    expect(backups.length).toBe(72)
    expect(activity.length).toBeGreaterThan(0)
    expect(settings.targets).toEqual({ rtoMinutes: 30, rpoMinutes: 60 })
  })

  it('blocks a second recovery while one is running (duplicate-job protection)', async () => {
    const p = provider()
    const latest = (await p.getOverview()).readiness.latestVerified!
    await p.startRecovery(latest.id)
    await expect(p.startRecovery(latest.id)).rejects.toMatchObject({ code: 'job-already-running' })
  })

  it('allows a new recovery once the previous one has finished', async () => {
    const p = provider()
    const latest = (await p.getOverview()).readiness.latestVerified!
    await p.startRecovery(latest.id)
    realNow = (TOTAL_SIMULATED_SECONDS / 100) * 1000 + 10
    await expect(p.startRecovery(latest.id)).resolves.toBeTruthy()
  })

  it('rejects unknown or unverified recovery points', async () => {
    const p = provider()
    const failed = (await p.listBackups()).find((b) => b.status === 'failed')!
    await expect(p.startRecovery('nope')).rejects.toMatchObject({ code: 'unknown-recovery-point' })
    await expect(p.startRecovery(failed.id)).rejects.toMatchObject({ code: 'recovery-point-not-verified' })
  })

  it('records simulated recovery events in the activity log', async () => {
    const p = provider()
    const latest = (await p.getOverview()).readiness.latestVerified!
    const job = await p.startRecovery(latest.id)
    realNow = (TOTAL_SIMULATED_SECONDS / 100) * 1000 + 10
    expect((await p.getRecoveryState(job.id)).status).toBe('succeeded')
    const recoveryEvents = (await p.listActivity()).filter((e) => e.category === 'recovery')
    expect(recoveryEvents.map((e) => e.title)).toEqual([
      'Simulated recovery finished',
      'Simulated recovery approved',
    ])
    expect(recoveryEvents.every((e) => e.simulated)).toBe(true)
  })

  it('stops a running simulation on request', async () => {
    const p = provider()
    const latest = (await p.getOverview()).readiness.latestVerified!
    const job = await p.startRecovery(latest.id)
    realNow = 1_000
    await p.cancelRecovery(job.id)
    realNow = 99_000
    expect((await p.getRecoveryState(job.id)).status).toBe('cancelled')
  })
})
