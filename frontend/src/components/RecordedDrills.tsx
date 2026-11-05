import { ExternalLink } from 'lucide-react'
import { motion } from 'motion/react'
import { RECORDED_DRILLS, type RecordedDrill } from '../data/recorded-drills'
import { usePrefs } from '../lib/context'
import * as f from '../lib/format'

const STAGE_COLORS = ['bg-sky/45', 'bg-gold/70', 'bg-sky', 'bg-accent/35', 'bg-accent/55', 'bg-accent/75', 'bg-accent', 'bg-accent-ink']

/**
 * Real, measured drill results (sanitized). Deliberately styled apart from the simulation: these numbers
 * come from recovery drills in AWS and link to their evidence.
 */
export function RecordedDrills({ compact = false }: { compact?: boolean }) {
  const [latest, ...earlier] = RECORDED_DRILLS
  if (!latest) return null
  return (
    <section className="panel flex flex-col gap-5 p-6" aria-labelledby="recorded-title" data-testid="recorded-drills">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="recorded-title" className="text-[18px] leading-6 font-semibold">
          Measured in real AWS drills
        </h2>
        <span className="rounded-full bg-tint px-2.5 py-0.5 text-[12px] font-medium text-accent-ink">Recorded results, not simulated</span>
      </div>
      <Latest drill={latest} compact={compact} />
      {!compact &&
        earlier.map((d) => (
          <p key={d.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-t border-rule pt-4 text-[13px] text-muted">
            <span className="text-ink">{d.title}</span>
            <span className="num">
              RTO {f.clock(Math.round(d.rtoSeconds))} · RPO {f.clock(Math.round(d.rpoSeconds))}
            </span>
            <span>{d.verification.toLowerCase()}</span>
            <Evidence href={d.evidence} />
          </p>
        ))}
    </section>
  )
}

function Latest({ drill: d, compact }: { drill: RecordedDrill; compact: boolean }) {
  const { prefs } = usePrefs()
  const total = d.stages.reduce((s, x) => s + x.seconds, 0)
  return (
    <div className="flex flex-col gap-4">
      <p className="text-[14px] leading-[22px] text-ink">
        <span className="font-semibold">{d.title}</span>
        <span className="text-muted">
          {' '}
          · {f.dateTime(d.date, prefs.timeZone)} · {d.criteria ?? d.kind}
        </span>
      </p>
      <dl className="grid grid-cols-2 gap-3">
        <Measure label="Recovery time (RTO)" value={f.clock(Math.round(d.rtoSeconds))} target={`target ${d.rtoTargetMinutes} min`} />
        <Measure label="Data lost (RPO)" value={f.clock(Math.round(d.rpoSeconds))} target={`target ${d.rpoTargetMinutes} min`} />
      </dl>

      <div>
        <div className="flex h-3 w-full overflow-hidden rounded-full bg-raised" aria-hidden="true">
          {d.stages.map((s, i) => (
            <motion.div
              key={s.label}
              className={`h-full ${STAGE_COLORS[i % STAGE_COLORS.length]}`}
              style={{ width: `${(s.seconds / total) * 100}%`, transformOrigin: 'left' }}
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ duration: 0.25, delay: 0.04 * i, ease: 'easeOut' }}
            />
          ))}
        </div>
        <ul className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1 text-[12px] sm:grid-cols-2" aria-label="Where the recovery time went">
          {d.stages.map((s, i) => (
            <li key={s.label} className="flex items-center gap-2">
              <span className={`size-2.5 flex-none rounded-sm ${STAGE_COLORS[i % STAGE_COLORS.length]}`} aria-hidden="true" />
              <span className="text-ink">{s.label}</span>
              <span className="num ml-auto text-muted">{f.clock(Math.round(s.seconds))}</span>
            </li>
          ))}
        </ul>
      </div>

      {!compact && <p className="max-w-[70ch] text-[13px] leading-5 text-muted">{d.note}</p>}
      <p className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-[12px] text-muted">
        <span>{d.verification}</span>
        <span className="num">
          {f.count(d.records.farmers)} members · {f.count(d.records.inventoryItems)} items · {f.count(d.records.transactions)} ledger entries restored
        </span>
        <span className="num">≈ USD {d.costUsd.toFixed(3)} of compute</span>
        <Evidence href={d.evidence} />
      </p>
    </div>
  )
}

function Measure({ label, value, target }: { label: string; value: string; target: string }) {
  return (
    <div className="rounded-lg bg-raised p-3">
      <dt className="text-[12px] text-muted">{label}</dt>
      <dd className="m-0 flex flex-wrap items-baseline gap-x-2">
        <span className="num text-[24px] leading-8 font-semibold text-ink">{value}</span>
        <span className="text-[12px] text-accent-ink">within {target}</span>
      </dd>
    </div>
  )
}

function Evidence({ href }: { href: string }) {
  return (
    <a href={href} target="_blank" rel="noreferrer noopener" className="btn btn-text inline-flex items-center gap-1 text-[12px]">
      Evidence
      <ExternalLink className="size-3" aria-hidden="true" />
      <span className="sr-only">(opens GitHub in a new tab)</span>
    </a>
  )
}
