import { describe, expect, it } from 'vitest'
import { DEMO_NOW, buildDemoDataset } from './demo-dataset'

const { backups, activity } = buildDemoDataset()

describe('demo dataset', () => {
  it('has one hourly slot per hour for 72 hours, newest first', () => {
    expect(backups).toHaveLength(72)
    for (let i = 1; i < backups.length; i++) {
      const gap = Date.parse(backups[i - 1]!.scheduledAt) - Date.parse(backups[i]!.scheduledAt)
      expect(gap).toBe(3_600_000)
    }
    expect(Date.parse(backups[0]!.scheduledAt)).toBeLessThanOrEqual(DEMO_NOW.getTime())
  })

  it('contains the scripted typhoon outage and one corrupted upload', () => {
    expect(backups.filter((b) => b.status === 'missed')).toHaveLength(3)
    expect(backups.filter((b) => b.status === 'failed')).toHaveLength(1)
    expect(backups.filter((b) => b.status === 'verified')).toHaveLength(68)
  })

  it('only verified backups carry a passing restore test and record counts', () => {
    for (const b of backups) {
      if (b.status === 'verified') {
        expect(b.checksum).toBe('match')
        expect(b.restoreTest).toBe('passed')
        expect(b.records).toBeDefined()
        expect(b.sizeBytes).toBeGreaterThan(0)
      } else {
        expect(b.restoreTest).not.toBe('passed')
        expect(b.failureReason).toBeTruthy()
      }
      if (b.status === 'missed') {
        expect(b.sizeBytes).toBeNull()
        expect(b.sha256).toBeNull()
      }
    }
  })

  it('ledger record counts never decrease over time', () => {
    const verifiedOldestFirst = backups.filter((b) => b.records).reverse()
    for (let i = 1; i < verifiedOldestFirst.length; i++) {
      expect(verifiedOldestFirst[i]!.records!.transactions).toBeGreaterThanOrEqual(
        verifiedOldestFirst[i - 1]!.records!.transactions,
      )
    }
  })

  it('activity is newest first and every backup reference resolves', () => {
    const ids = new Set(backups.map((b) => b.id))
    for (let i = 1; i < activity.length; i++) {
      expect(Date.parse(activity[i - 1]!.at)).toBeGreaterThanOrEqual(Date.parse(activity[i]!.at))
    }
    for (const e of activity) if (e.backupId) expect(ids.has(e.backupId)).toBe(true)
    expect(activity.some((e) => e.severity === 'error')).toBe(true)
    expect(activity.some((e) => e.severity === 'warning')).toBe(true)
  })

  it('is deterministic', () => {
    expect(buildDemoDataset()).toEqual(buildDemoDataset())
  })
})
