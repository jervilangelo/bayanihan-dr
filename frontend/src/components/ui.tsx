import { motion, type Variants } from 'motion/react'
import type { ReactNode } from 'react'
import type { BackupStatus, Severity } from '../data/types'

/* ---------- motion: short, opacity + a few pixels, dropped under reduced motion ---------- */

const container: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.045 } } }
const item: Variants = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.22, ease: [0.2, 0, 0, 1] } },
}

/** Staggered entrance for a page's blocks. Content is never hidden if motion is unavailable. */
export function Stagger({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div className={className} variants={container} initial="hidden" animate="show">
      {children}
    </motion.div>
  )
}

export function StaggerItem({ children, className, as = 'div' }: { children: ReactNode; className?: string; as?: 'div' | 'li' }) {
  const Tag = as === 'li' ? motion.li : motion.div
  return (
    <Tag className={className} variants={item}>
      {children}
    </Tag>
  )
}

/* ---------- page header ---------- */

export function PageHeader({ title, subline, action }: { title: string; subline?: ReactNode; action?: ReactNode }) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-[28px] leading-9 font-bold tracking-[-0.01em] text-ink lg:text-[32px] lg:leading-10">{title}</h1>
        {subline && <p className="mt-1 max-w-[72ch] text-[15px] leading-6 text-muted">{subline}</p>}
      </div>
      {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
    </header>
  )
}

export function SectionTitle({ children, aside, id }: { children: ReactNode; aside?: ReactNode; id?: string }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-4">
      <h2 id={id} className="text-[18px] leading-6 font-semibold text-ink">
        {children}
      </h2>
      {aside && <div className="text-[13px] text-muted">{aside}</div>}
    </div>
  )
}

/* ---------- status marks ---------- */

const BACKUP_PILL: Record<BackupStatus, { label: string; cls: string }> = {
  verified: { label: 'Verified', cls: 'bg-tint text-accent-ink' },
  pending: { label: 'Verifying', cls: 'bg-sky-tint text-sky-ink' },
  failed: { label: 'Rejected', cls: 'bg-neg-bg text-neg-ink' },
  missed: { label: 'Missed', cls: 'bg-raised text-muted' },
}

export function BackupPill({ status }: { status: BackupStatus }) {
  const p = BACKUP_PILL[status]
  return (
    <span className={`inline-flex h-[22px] flex-none items-center rounded-full px-2.5 text-[12px] font-medium whitespace-nowrap ${p.cls}`}>
      {p.label}
    </span>
  )
}

const SEVERITY: Record<Severity, { label: string; dot: string }> = {
  info: { label: 'Info', dot: 'bg-accent' },
  warning: { label: 'Warning', dot: 'bg-gold' },
  error: { label: 'Error', dot: 'bg-neg' },
}

export function SeverityDot({ severity }: { severity: Severity }) {
  return (
    <span className="inline-flex items-center" title={SEVERITY[severity].label}>
      <span className={`size-2 rounded-full ${SEVERITY[severity].dot}`} aria-hidden="true" />
      <span className="sr-only">{SEVERITY[severity].label}</span>
    </span>
  )
}

export function SimulatedTag({ children = 'Simulated' }: { children?: ReactNode }) {
  return (
    <span className="inline-flex h-[22px] flex-none items-center rounded-full border border-warn-border bg-warn-bg px-2.5 text-[12px] font-medium whitespace-nowrap text-warn-ink">
      {children}
    </span>
  )
}

/* ---------- loading and error ---------- */

export function Skeleton({ w, h = 14, className = '' }: { w: number | string; h?: number; className?: string }) {
  return <span className={`skeleton ${className}`} style={{ width: w, height: h }} aria-hidden="true" />
}

export function Loading({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="status" aria-live="polite" aria-busy="true">
      <span className="sr-only">Loading {label}…</span>
      {children}
    </div>
  )
}

export function BlockError({ what, onRetry }: { what: string; onRetry: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-neg-bg bg-surface px-4 py-3">
      <span className="size-2 rounded-full bg-neg" aria-hidden="true" />
      <span className="text-ink">Couldn't load {what}.</span>
      <button type="button" className="btn btn-text" onClick={onRetry}>
        Retry
      </button>
    </div>
  )
}
