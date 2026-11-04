import type { Backup, Readiness } from './types'

const HOUR = 3_600_000

/**
 * "Are we protected?" Only a backup that passed BOTH checksum and a test restore counts as a
 * recovery point (blueprint §9: never mark unverified backups as protected).
 */
export function readinessOf(backups: Backup[], now: Date, rpoTargetMinutes: number): Readiness {
  const counts = { verified: 0, pending: 0, failed: 0, missed: 0 }
  for (const b of backups) counts[b.status]++

  const latestVerified =
    [...backups]
      .filter((b) => b.status === 'verified' && b.restoreTest === 'passed')
      .sort((a, b) => Date.parse(b.scheduledAt) - Date.parse(a.scheduledAt))[0] ?? null

  if (!latestVerified) {
    return { state: 'no-recovery-point', latestVerified: null, recoveryPointAgeMinutes: null, rpoTargetMinutes, counts }
  }
  const age = Math.floor((now.getTime() - Date.parse(latestVerified.scheduledAt)) / 60_000)
  return {
    state: age <= rpoTargetMinutes ? 'protected' : 'outside-target',
    latestVerified,
    recoveryPointAgeMinutes: age,
    rpoTargetMinutes,
    counts,
  }
}

export interface HourSlot {
  /** Start of the hour (UTC ISO). */
  hourStart: string
  backup: Backup | null
}

/** One slot per clock hour for the last `hours` hours, oldest first, ending with the current hour. */
export function hourlySlots(backups: Backup[], now: Date, hours: number): HourSlot[] {
  const currentHour = Math.floor(now.getTime() / HOUR) * HOUR
  const byHour = new Map<number, Backup>()
  for (const b of backups) byHour.set(Math.floor(Date.parse(b.scheduledAt) / HOUR) * HOUR, b)

  return Array.from({ length: hours }, (_, i) => {
    const start = currentHour - (hours - 1 - i) * HOUR
    return { hourStart: new Date(start).toISOString(), backup: byHour.get(start) ?? null }
  })
}
