import type { ActivityEvent, Backup } from './types'

/**
 * SYNTHETIC demo data for the public dashboard. Nothing here is a measurement.
 *
 * The demo runs on a fixed clock so every visitor (and every test) sees the same story:
 * hourly backups for the last 72 hours, a typhoon power cut that made three backups miss their
 * schedule, and one upload whose checksum did not match. Record counts start from the Phase 1
 * seed dataset (1,050 members, 26 items, 3,000 ledger entries) and grow with business hours.
 */
export const DEMO_NOW = new Date('2026-11-04T05:52:00Z') // 13:52 Philippine time
const HOUR = 3_600_000
const LATEST_SLOT = Date.parse('2026-11-04T05:05:00Z') // 13:05 PHT
const SLOTS = 72

/** Slot indexes counted back from the newest (0 = 13:05 today). */
const MISSED = new Map<number, string>([
  // 20:05, 21:05 and 22:05 PHT yesterday
  [15, 'Office power was out (typhoon rains); the backup job did not run.'],
  [16, 'Office power was out (typhoon rains); the backup job did not run.'],
  [17, 'Office power was out (typhoon rains); the backup job did not run.'],
])
const FAILED = new Map<number, string>([
  [9, 'Checksum mismatch after upload; the copy was rejected and not used as a recovery point.'],
])

function phtHour(ms: number): number {
  return (new Date(ms).getUTCHours() + 8) % 24
}

/** Small deterministic hash so sample checksums look like checksums and never change between loads. */
function sampleSha256(seed: string): string {
  let out = ''
  let h = 2166136261
  for (let round = 0; out.length < 64; round++) {
    for (const ch of `${seed}:${round}`) h = Math.imul(h ^ ch.charCodeAt(0), 16777619) >>> 0
    out += h.toString(16).padStart(8, '0')
  }
  return out.slice(0, 64)
}

export function buildDemoDataset(): { backups: Backup[]; activity: ActivityEvent[] } {
  const oldestFirst: Backup[] = []
  let transactions = 3000
  let farmers = 1050

  for (let i = SLOTS - 1; i >= 0; i--) {
    const scheduled = LATEST_SLOT - i * HOUR
    const hour = phtHour(scheduled)
    // Business hours (08:00-17:00 PHT) add ledger entries; one new member joins each morning.
    if (hour >= 8 && hour <= 17) transactions += 3 + ((i * 7) % 4)
    if (hour === 9) farmers += 1

    const id = `bk-${new Date(scheduled).toISOString().slice(0, 13).replaceAll('-', '').replace('T', '-')}`
    const base = { id, scheduledAt: new Date(scheduled).toISOString(), schemaRevision: '0001' }
    const missed = MISSED.get(i)
    const failed = FAILED.get(i)

    if (missed) {
      oldestFirst.push({
        ...base, status: 'missed', completedAt: null, sizeBytes: null, sha256: null,
        checksum: 'not-run', restoreTest: 'not-run', offsite: 'not-stored', failureReason: missed,
      })
      continue
    }
    const sizeBytes = 285_000 + transactions * 38 + farmers * 61
    const completedAt = new Date(scheduled + (38 + (i % 9)) * 1000).toISOString()
    if (failed) {
      oldestFirst.push({
        ...base, status: 'failed', completedAt, sizeBytes, sha256: sampleSha256(id),
        checksum: 'mismatch', restoreTest: 'not-run', offsite: 'rejected', failureReason: failed,
      })
      continue
    }
    oldestFirst.push({
      ...base, status: 'verified', completedAt, sizeBytes, sha256: sampleSha256(id),
      checksum: 'match', restoreTest: 'passed', offsite: 'stored',
      records: { farmers, inventoryItems: 26, transactions },
    })
  }

  const backups = oldestFirst.reverse()
  return { backups, activity: activityFor(backups) }
}

function activityFor(backups: Backup[]): ActivityEvent[] {
  const events: ActivityEvent[] = []
  const add = (e: Omit<ActivityEvent, 'id' | 'simulated'>) =>
    events.push({ ...e, id: `ev-${events.length + 1}`, simulated: true })

  for (const b of backups) {
    const done = b.completedAt ?? b.scheduledAt
    if (b.status === 'missed') {
      add({ at: b.scheduledAt, category: 'backup', severity: 'warning', title: 'Scheduled backup missed', detail: b.failureReason!, actor: 'Backup scheduler', backupId: b.id })
    } else if (b.status === 'failed') {
      add({ at: done, category: 'backup', severity: 'error', title: 'Backup rejected', detail: b.failureReason!, actor: 'Backup verifier', backupId: b.id })
    } else {
      add({ at: done, category: 'backup', severity: 'info', title: 'Backup verified', detail: `Checksum matched and a test restore found ${b.records!.transactions.toLocaleString('en-PH')} ledger entries.`, actor: 'Backup verifier', backupId: b.id })
    }
    const hour = phtHour(Date.parse(b.scheduledAt))
    if (hour === 1) {
      add({ at: new Date(Date.parse(b.scheduledAt) + 20 * 60_000).toISOString(), category: 'audit', severity: 'info', title: 'Retention applied', detail: 'Backups older than 72 hours were removed from the hourly set.', actor: 'Backup scheduler' })
      add({ at: new Date(Date.parse(b.scheduledAt) + 25 * 60_000).toISOString(), category: 'infrastructure', severity: 'info', title: 'Recovery environment idle', detail: 'No AWS recovery resources are running (cold standby); nothing is being billed for compute.', actor: 'Environment check' })
    }
  }
  // The power came back after the outage: the scheduler resumed with the next hourly run.
  const firstAfterOutage = backups.find((b, idx) => b.status !== 'missed' && backups[idx + 1]?.status === 'missed')
  if (firstAfterOutage) {
    add({ at: new Date(Date.parse(firstAfterOutage.scheduledAt) - 25 * 60_000).toISOString(), category: 'backup', severity: 'info', title: 'Backup schedule resumed', detail: 'Office power restored; the next hourly backup ran on time.', actor: 'Backup scheduler' })
  }
  return events.sort((a, b) => Date.parse(b.at) - Date.parse(a.at))
}
