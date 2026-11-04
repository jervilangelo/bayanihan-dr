import { describe, expect, it } from 'vitest'
import { RECOVERY_STEPS, TOTAL_SIMULATED_SECONDS, createSimulatedJob, jobStateAt } from './simulation'
import type { Backup } from './types'

const declaredAt = new Date('2026-11-04T05:52:00Z')
const point: Backup = {
  id: 'bk-x',
  scheduledAt: '2026-11-04T05:05:00Z',
  completedAt: '2026-11-04T05:05:41Z',
  status: 'verified',
  sizeBytes: 400_000,
  sha256: 'cd'.repeat(32),
  checksum: 'match',
  restoreTest: 'passed',
  offsite: 'stored',
  records: { farmers: 1050, inventoryItems: 26, transactions: 3120 },
  schemaRevision: '0001',
}

describe('recovery simulation', () => {
  it('follows the blueprint recovery sequence', () => {
    expect(RECOVERY_STEPS.map((s) => s.id)).toEqual([
      'declare', 'access', 'approve', 'provision', 'bootstrap', 'download',
      'restore', 'start', 'health', 'validate', 'report',
    ])
    expect(TOTAL_SIMULATED_SECONDS).toBe(RECOVERY_STEPS.reduce((n, s) => n + s.simulatedSeconds, 0))
  })

  it('uses whole-minute steps so the minutes shown per step add up to the total shown', () => {
    expect(RECOVERY_STEPS.every((s) => s.simulatedSeconds % 60 === 0)).toBe(true)
  })

  it('refuses a recovery point that is not verified', () => {
    expect(() => createSimulatedJob({ ...point, status: 'failed' }, declaredAt, 0, 100)).toThrow(/verified/)
  })

  it('starts with the first step running', () => {
    const job = createSimulatedJob(point, declaredAt, 0, 100)
    const state = jobStateAt(job, 0)
    expect(state.status).toBe('running')
    expect(state.steps[0]!.status).toBe('running')
    expect(state.steps.slice(1).every((s) => s.status === 'pending')).toBe(true)
  })

  it('advances by simulated time at the playback speed', () => {
    const job = createSimulatedJob(point, declaredAt, 1_000, 100)
    // 1.9 real seconds at 100x = 190 simulated seconds: declare (60) + access (120) done, approve running
    const state = jobStateAt(job, 1_000 + 1_900)
    expect(state.steps.map((s) => s.status).slice(0, 4)).toEqual(['done', 'done', 'running', 'pending'])
    expect(state.simulatedElapsedSeconds).toBe(190)
  })

  it('finishes with a result measured against the targets', () => {
    const job = createSimulatedJob(point, declaredAt, 0, 100)
    const state = jobStateAt(job, (TOTAL_SIMULATED_SECONDS / 100) * 1000 + 50)
    expect(state.status).toBe('succeeded')
    expect(state.steps.every((s) => s.status === 'done')).toBe(true)
    expect(state.simulatedElapsedSeconds).toBe(TOTAL_SIMULATED_SECONDS)
    expect(state.result).toEqual({
      simulated: true,
      recoveryMinutes: TOTAL_SIMULATED_SECONDS / 60,
      dataLossMinutes: 47,
      rtoTargetMinutes: 30,
      rpoTargetMinutes: 60,
      withinRto: TOTAL_SIMULATED_SECONDS / 60 <= 30,
      withinRpo: true,
      recordsValidated: point.records,
    })
  })

  it('can be cancelled and then stops advancing', () => {
    const job = createSimulatedJob(point, declaredAt, 0, 100)
    job.cancelledAtRealMs = 500
    const state = jobStateAt(job, 60_000)
    expect(state.status).toBe('cancelled')
    expect(state.simulatedElapsedSeconds).toBe(50)
    expect(state.result).toBeNull()
  })
})
