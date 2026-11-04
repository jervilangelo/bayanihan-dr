import { describe, expect, it } from 'vitest'
import type { Backup } from './types'
import { hourlySlots, readinessOf } from './readiness'

const NOW = new Date('2026-11-04T05:52:00Z')

function backup(hoursAgo: number, status: Backup['status'], minutePast = 5): Backup {
  const at = new Date(NOW)
  at.setUTCMinutes(minutePast, 0, 0)
  at.setUTCHours(at.getUTCHours() - hoursAgo)
  const verified = status === 'verified'
  return {
    id: `bk-${hoursAgo}`,
    scheduledAt: at.toISOString(),
    completedAt: status === 'missed' ? null : at.toISOString(),
    status,
    sizeBytes: status === 'missed' ? null : 400_000,
    sha256: status === 'missed' ? null : 'ab'.repeat(32),
    checksum: verified ? 'match' : status === 'failed' ? 'mismatch' : 'not-run',
    restoreTest: verified ? 'passed' : 'not-run',
    offsite: verified ? 'stored' : 'not-stored',
    records: verified ? { farmers: 1050, inventoryItems: 26, transactions: 3000 } : undefined,
    failureReason: verified ? undefined : 'test',
    schemaRevision: '0001',
  }
}

describe('readinessOf', () => {
  it('uses the newest VERIFIED backup, skipping failed and missed ones', () => {
    const r = readinessOf([backup(0, 'failed'), backup(1, 'missed'), backup(2, 'verified')], NOW, 60)
    expect(r.latestVerified?.id).toBe('bk-2')
    expect(r.recoveryPointAgeMinutes).toBe(167)
    expect(r.state).toBe('outside-target')
  })

  it('is protected when the newest verified point is inside the RPO target', () => {
    const r = readinessOf([backup(0, 'verified')], NOW, 60)
    expect(r.recoveryPointAgeMinutes).toBe(47)
    expect(r.state).toBe('protected')
  })

  it('is at risk with no verified backup at all', () => {
    const r = readinessOf([backup(0, 'failed')], NOW, 60)
    expect(r.latestVerified).toBeNull()
    expect(r.recoveryPointAgeMinutes).toBeNull()
    expect(r.state).toBe('no-recovery-point')
  })

  it('counts outcomes over the window it is given', () => {
    const r = readinessOf([backup(0, 'verified'), backup(1, 'failed'), backup(2, 'missed'), backup(3, 'missed')], NOW, 60)
    expect(r.counts).toEqual({ verified: 1, failed: 1, missed: 2 })
  })
})

describe('hourlySlots', () => {
  it('returns one slot per hour for the last 24 hours, oldest first', () => {
    const backups = Array.from({ length: 30 }, (_, h) => backup(h, h === 3 ? 'failed' : 'verified'))
    const slots = hourlySlots(backups, NOW, 24)
    expect(slots).toHaveLength(24)
    expect(slots.at(-1)!.backup?.id).toBe('bk-0')
    expect(slots.at(-4)!.backup?.status).toBe('failed')
  })

  it('marks an hour with no record as empty rather than inventing one', () => {
    const slots = hourlySlots([backup(0, 'verified')], NOW, 24)
    expect(slots.filter((s) => s.backup === null)).toHaveLength(23)
  })
})
