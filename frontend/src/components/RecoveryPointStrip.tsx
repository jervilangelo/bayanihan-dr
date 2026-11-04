import { motion } from 'motion/react'
import { hourlySlots } from '../data/readiness'
import type { Backup } from '../data/types'
import * as f from '../lib/format'
import { usePrefs } from '../lib/context'

const HOURS = 24
const SPAN_MS = HOURS * 3_600_000

/**
 * Signature element: the last 24 hours of recovery points on one time axis, with the RPO window
 * (the most data the cooperative can afford to lose) shaded back from "now". A verified point inside
 * the window means "protected"; the hatch marks hours when no backup ran.
 */
export function RecoveryPointStrip({ backups, now, rpoMinutes }: { backups: Backup[]; now: Date; rpoMinutes: number }) {
  const { prefs } = usePrefs()
  const end = now.getTime()
  const start = end - SPAN_MS
  const x = (ms: number) => ((ms - start) / SPAN_MS) * 100
  const slots = hourlySlots(backups, now, HOURS + 1).filter((s) => Date.parse(s.hourStart) + 3_600_000 > start)
  const windowLeft = x(end - rpoMinutes * 60_000)
  const latestVerified = backups.find((b) => b.status === 'verified')
  // A label every four clock hours, kept clear of the "Now" label at the right end.
  const ticks = slots
    .map((s) => Date.parse(s.hourStart))
    .filter((ms) => ms > start && x(ms) < 88 && Number(f.time(new Date(ms).toISOString(), prefs.timeZone).slice(0, 2)) % 4 === 0)

  const counts = { verified: 0, pending: 0, failed: 0, missed: 0 }
  for (const s of slots) if (s.backup && Date.parse(s.backup.scheduledAt) >= start) counts[s.backup.status]++

  return (
    <figure className="m-0">
      <figcaption className="sr-only">
        Recovery points in the last 24 hours: {counts.verified} verified, {counts.failed} rejected, {counts.missed} missed.
        The newest verified point is from {latestVerified ? f.time(latestVerified.scheduledAt, prefs.timeZone) : 'none'}.
      </figcaption>

      <div className="relative h-[86px]" aria-hidden="true">
        {/* RPO window, shaded back from now */}
        <div
          className="absolute top-5 bottom-6 rounded-[3px] bg-sky-tint"
          style={{ left: `${windowLeft}%`, right: 0 }}
        />
        <div className="absolute top-0 text-[12px] leading-4 whitespace-nowrap text-sky-ink" style={{ right: 0 }}>
          {rpoMinutes / 60}-hour target window
        </div>

        {/* one mark per scheduled backup, positioned at its real time */}
        {slots.map((s, i) => {
          if (!s.backup) return null
          const t = Date.parse(s.backup.scheduledAt)
          if (t < start) return null
          const cls =
            s.backup.status === 'verified'
              ? 'bg-accent'
              : s.backup.status === 'failed'
                ? 'bg-surface border-2 border-neg'
                : s.backup.status === 'pending'
                  ? 'bg-surface border-2 border-sky'
                  : 'hatch border border-control'
          return (
            <motion.div
              key={s.backup.id}
              className={`absolute top-7 bottom-8 rounded-[2px] ${cls}`}
              style={{ left: `${x(t)}%`, width: `calc(${100 / HOURS}% - 5px)`, originY: 1 }}
              initial={{ opacity: 0, scaleY: 0.4 }}
              animate={{ opacity: 1, scaleY: 1 }}
              transition={{ duration: 0.2, delay: i * 0.012, ease: [0.2, 0, 0, 1] }}
            />
          )
        })}

        {/* now */}
        <div className="absolute top-4 bottom-6 w-[2px] bg-sky-ink" style={{ right: 0 }} />

        {/* axis */}
        <div className="absolute inset-x-0 bottom-6 h-px bg-border" />
        {ticks.map((ms) => (
          <div key={ms} className="absolute bottom-0 -translate-x-1/2 text-[12px] leading-4 text-muted num" style={{ left: `${x(ms)}%` }}>
            {f.time(new Date(ms).toISOString(), prefs.timeZone)}
          </div>
        ))}
        <div className="absolute right-0 bottom-0 text-[12px] leading-4 font-medium text-ink num">
          Now {f.time(now.toISOString(), prefs.timeZone)}
        </div>
      </div>

      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-[13px] text-muted" aria-label="Legend">
        <li className="flex items-center gap-2">
          <span className="h-3 w-2 rounded-[2px] bg-accent" aria-hidden="true" /> Verified point
          <span className="text-ink num">{counts.verified}</span>
        </li>
        <li className="flex items-center gap-2">
          <span className="h-3 w-2 rounded-[2px] border-2 border-neg" aria-hidden="true" /> Rejected
          <span className="text-ink num">{counts.failed}</span>
        </li>
        <li className="flex items-center gap-2">
          <span className="hatch h-3 w-2 rounded-[2px] border border-control" aria-hidden="true" /> Missed
          <span className="text-ink num">{counts.missed}</span>
        </li>
      </ul>
    </figure>
  )
}
