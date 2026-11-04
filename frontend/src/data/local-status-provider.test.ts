import { describe, expect, it } from 'vitest'
import { createLocalStatusProvider, parseEngineStatus, type EngineStatus } from './local-status-provider'
import { ProviderError, type Backup } from './types'

const NOW = new Date('2026-11-04T08:20:00Z')

function backup(id: string, scheduledAt: string, status: Backup['status']): Backup {
  return {
    id,
    scheduledAt,
    completedAt: scheduledAt,
    status,
    sizeBytes: 52_000,
    sha256: status === 'missed' ? null : 'ab'.repeat(32),
    checksum: status === 'verified' ? 'match' : 'not-run',
    restoreTest: status === 'verified' ? 'passed' : 'not-run',
    offsite: 'not-stored',
    schemaRevision: '0001',
    records: { farmers: 120, inventoryItems: 40, transactions: 600 },
  }
}

const STATUS: EngineStatus = {
  schemaVersion: 1,
  generatedAt: '2026-11-04T08:19:00Z',
  mode: 'operational',
  primary: { name: 'BFC office server', location: 'Naga City office', status: 'online', checkedAt: '2026-11-04T08:19:00Z', schemaRevision: '0001' },
  targets: { rtoMinutes: 30, rpoMinutes: 60 },
  schedule: { intervalMinutes: 60, description: 'Every hour, on the hour' },
  retention: { description: 'All backups for 24 hours…' },
  restoreTest: 'Every backup is restored into a disposable database.',
  database: 'cms',
  backups: [
    backup('20261104T080000Z', '2026-11-04T08:00:00Z', 'pending'),
    backup('20261104T070000Z', '2026-11-04T07:00:00Z', 'verified'),
    backup('20261104T060000Z', '2026-11-04T06:00:00Z', 'failed'),
  ],
  activity: [],
}

const fetchOf = (body: unknown, status = 200) =>
  (async () => new Response(JSON.stringify(body), { status })) as unknown as typeof fetch

describe('local status provider', () => {
  it('only counts verified backups as recovery points, never pending ones', async () => {
    const p = createLocalStatusProvider({ url: '/x', fetchImpl: fetchOf(STATUS), now: () => NOW })
    const o = await p.getOverview()
    expect(p.mode).toBe('operational')
    expect(o.readiness.latestVerified?.id).toBe('20261104T070000Z')
    expect(o.readiness.recoveryPointAgeMinutes).toBe(80)
    expect(o.readiness.state).toBe('outside-target')
    expect(o.readiness.counts).toEqual({ verified: 1, pending: 1, failed: 1, missed: 0 })
  })

  it('reports settings as operational and decided', async () => {
    const s = await createLocalStatusProvider({ url: '/x', fetchImpl: fetchOf(STATUS) }).getSettings()
    expect(s.mode).toBe('operational')
    expect(s.retention.decided).toBe(true)
    expect(s.schedule.expression).toBe('every 60 min')
  })

  it('refuses every recovery operation', async () => {
    const p = createLocalStatusProvider({ url: '/x', fetchImpl: fetchOf(STATUS) })
    await expect(p.startRecovery('20261104T070000Z')).rejects.toMatchObject({ code: 'recovery-unavailable' })
    await expect(p.cancelRecovery('j')).rejects.toBeInstanceOf(ProviderError)
    expect(await p.activeRecovery()).toBeNull()
  })

  it('explains a missing status file', async () => {
    const p = createLocalStatusProvider({ url: '/x', fetchImpl: fetchOf({}, 404) })
    await expect(p.listBackups()).rejects.toThrow(/Run the backup engine once/)
  })

  it('rejects an unknown status schema', () => {
    expect(() => parseEngineStatus({ ...STATUS, schemaVersion: 2 })).toThrow(ProviderError)
    expect(() => parseEngineStatus(null)).toThrow(ProviderError)
  })
})
