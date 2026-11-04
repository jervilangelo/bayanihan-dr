import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router'
import { RecoveryPointStrip } from '../components/RecoveryPointStrip'
import { BlockError, Loading, PageHeader, SectionTitle, SeverityDot, Skeleton, Stagger, StaggerItem } from '../components/ui'
import type { ActivityEvent, Backup, DashboardProvider, Overview as OverviewData } from '../data/types'
import { usePrefs, useResource } from '../lib/context'
import * as f from '../lib/format'

const loadOverview = (p: DashboardProvider) => Promise.all([p.getOverview(), p.listBackups(), p.listActivity()])

const STATE_COPY = {
  protected: { label: 'Protected', cls: 'bg-tint text-accent-ink' },
  'outside-target': { label: 'Outside target', cls: 'bg-warn-bg text-warn-ink' },
  'no-recovery-point': { label: 'No recovery point', cls: 'bg-neg-bg text-neg-ink' },
} as const

export function OverviewPage() {
  const res = useResource(loadOverview)
  const { prefs } = usePrefs()
  const [overview, backups, activity] = res.data ?? [null, null, null]

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Overview"
        subline={overview ? <Finding overview={overview} backups={backups!} /> : 'Checking the latest recovery point…'}
        action={
          <Link to="/recovery" className="btn btn-primary">
            Plan a recovery <ArrowRight size={16} aria-hidden="true" />
          </Link>
        }
      />

      {res.error && <BlockError what="the overview" onRetry={res.retry} />}
      {res.loading && <OverviewSkeleton />}

      {overview && backups && activity && (
        <Stagger className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="flex min-w-0 flex-col gap-6">
            <StaggerItem>
              <section className="panel p-5 sm:p-6" aria-labelledby="readiness-title">
                <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h2 id="readiness-title" className="text-[14px] leading-5 text-muted">
                      Age of the newest verified recovery point
                    </h2>
                    <div className="mt-1 flex items-baseline gap-3">
                      <span className="num text-[36px] leading-[44px] font-semibold tracking-[-0.02em] text-ink">
                        {overview.readiness.recoveryPointAgeMinutes === null ? '—' : f.duration(overview.readiness.recoveryPointAgeMinutes)}
                      </span>
                      <span className={`inline-flex h-6 items-center rounded-full px-2.5 text-[12px] font-medium ${STATE_COPY[overview.readiness.state].cls}`}>
                        {STATE_COPY[overview.readiness.state].label}
                      </span>
                    </div>
                    <p className="mt-1 text-[13px] text-muted">
                      {overview.readiness.latestVerified
                        ? `Backup of ${f.time(overview.readiness.latestVerified.scheduledAt, prefs.timeZone)}, checksum matched and test-restored. Target: no more than ${f.duration(overview.targets.rpoMinutes)} of data lost.`
                        : 'No backup has passed verification. A recovery now would have nothing safe to restore.'}
                    </p>
                  </div>
                  <dl className="grid shrink-0 grid-cols-[auto_auto] justify-start gap-x-6 gap-y-1 text-[13px] whitespace-nowrap sm:text-right">
                    <dt className="text-muted">Office server</dt>
                    <dd className="m-0 font-medium text-ink">
                      {overview.primary.status === 'online' ? 'Online' : 'Unreachable'}
                    </dd>
                    <dt className="text-muted">Checked</dt>
                    <dd className="num m-0 text-ink">{f.time(overview.primary.checkedAt, prefs.timeZone)}</dd>
                  </dl>
                </div>
                <div className="mt-6">
                  <RecoveryPointStrip backups={backups} now={new Date(overview.generatedAt)} rpoMinutes={overview.targets.rpoMinutes} />
                </div>
              </section>
            </StaggerItem>

            <StaggerItem>
              <section aria-labelledby="figures-title">
                <h2 id="figures-title" className="sr-only">Key figures</h2>
                <dl className="panel grid grid-cols-2 sm:grid-cols-4">
                  <Figure label="Recovery time target" value={f.duration(overview.targets.rtoMinutes)} note="Not yet measured in a drill" />
                  <Figure label="Data-loss target" value={f.duration(overview.targets.rpoMinutes)} note="Hourly backups" />
                  <Figure
                    label="Verified, last 72 h"
                    value={`${overview.readiness.counts.verified}`}
                    unit={` /${backups.length}`}
                    note="Usable recovery points"
                  />
                  <Figure
                    label="Problems, last 72 h"
                    value={`${overview.readiness.counts.failed + overview.readiness.counts.missed}`}
                    note={`${overview.readiness.counts.missed} missed, ${overview.readiness.counts.failed} rejected`}
                  />
                </dl>
              </section>
            </StaggerItem>

            <StaggerItem>
              <DailyRecord backups={backups} />
            </StaggerItem>
          </div>

          <StaggerItem className="flex min-w-0 flex-col gap-6">
            <ScheduleCard backups={backups} now={overview.generatedAt} />
            <RecentActivity events={activity.slice(0, 4)} />
          </StaggerItem>
        </Stagger>
      )}
    </div>
  )
}

function Finding({ overview, backups }: { overview: OverviewData; backups: Backup[] }) {
  const { prefs } = usePrefs()
  const r = overview.readiness
  if (!r.latestVerified) return <>No verified recovery point. Run and verify a backup before anything else.</>
  const recent = backups.slice(0, 24)
  const missed = recent.filter((b) => b.status === 'missed')
  const rejected = recent.filter((b) => b.status === 'failed')
  const issues = [
    missed.length ? `${missed.length} backups missed during last night's power cut` : '',
    rejected.length ? `${rejected.length} rejected at ${f.time(rejected[0]!.scheduledAt, prefs.timeZone)}` : '',
  ].filter(Boolean)
  return (
    <>
      {r.state === 'protected' ? 'Protected: ' : 'Attention: '}
      the newest verified backup is from {f.time(r.latestVerified.scheduledAt, prefs.timeZone)}, {r.recoveryPointAgeMinutes} minutes ago
      {r.state === 'protected' ? ', inside the 1-hour target.' : ', outside the 1-hour target.'}
      {issues.length > 0 && ` In the last 24 hours, ${issues.join(' and ')}.`}
    </>
  )
}

function Figure({ label, value, unit, note }: { label: string; value: string; unit?: string; note: string }) {
  return (
    <div className="border-border px-5 py-4 [&:not(:last-child)]:border-b sm:[&:not(:last-child)]:border-r sm:[&:not(:last-child)]:border-b-0 max-sm:odd:border-r">
      <dt className="text-[13px] text-muted">{label}</dt>
      <dd className="m-0 mt-1">
        <span className="num text-[24px] leading-8 font-medium text-ink">{value}</span>
        {unit && <span className="num text-[14px] text-muted">{unit}</span>}
        <span className="mt-0.5 block text-[12px] leading-4 text-muted">{note}</span>
      </dd>
    </div>
  )
}

/** Is the schedule reliable? One row per day, the hours as a 100% bar of verified, rejected and missed. */
function DailyRecord({ backups }: { backups: Backup[] }) {
  const { prefs } = usePrefs()
  const days = new Map<string, Backup[]>()
  for (const b of backups) {
    const key = f.day(b.scheduledAt, prefs.timeZone)
    days.set(key, [...(days.get(key) ?? []), b])
  }
  return (
    <section className="panel p-5 sm:p-6" aria-labelledby="daily-title">
      <SectionTitle id="daily-title" aside={<Link to="/backups" className="btn btn-text">All backups</Link>}>
        Backup record by day
      </SectionTitle>
      <ul className="flex flex-col gap-3">
        {[...days.entries()].map(([dayLabel, list]) => {
          const v = list.filter((b) => b.status === 'verified').length
          const r = list.filter((b) => b.status === 'failed').length
          const m = list.filter((b) => b.status === 'missed').length
          return (
            <li key={dayLabel} className="grid grid-cols-[88px_1fr_auto] items-center gap-4">
              <span className="text-[13px] text-ink">{dayLabel}</span>
              <span className="flex h-2.5 gap-[2px] overflow-hidden rounded-full" aria-hidden="true">
                <span className="bg-accent" style={{ flexGrow: v }} />
                {r > 0 && <span className="bg-neg" style={{ flexGrow: r }} />}
                {m > 0 && <span className="hatch border border-control" style={{ flexGrow: m }} />}
              </span>
              <span className="num text-right text-[13px] text-muted">
                <span className="text-ink">{v}</span> of {list.length} verified
                <span className="sr-only">, {r} rejected, {m} missed</span>
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/** When does the window refresh, and is the newest copy really off-site? */
function ScheduleCard({ backups, now }: { backups: Backup[]; now: string }) {
  const { prefs } = usePrefs()
  const nowMs = Date.parse(now)
  const latest = backups[0]
  const next = latest ? Date.parse(latest.scheduledAt) + 3_600_000 : null
  const lastVerified = backups.find((b) => b.status === 'verified')
  const stored = backups.filter((b) => b.offsite === 'stored').length
  const rows: [string, string, string][] = [
    ['Next backup', next ? f.time(new Date(next).toISOString(), prefs.timeZone) : '—', next ? `in ${f.duration(Math.max(0, Math.round((next - nowMs) / 60_000)))}` : ''],
    ['Last test restore', lastVerified?.completedAt ? f.time(lastVerified.completedAt, prefs.timeZone) : '—', lastVerified ? 'Passed' : 'None yet'],
    ['Off-site copies', `${stored}`, 'Encrypted, outside the office'],
  ]
  return (
    <section aria-labelledby="schedule-title">
      <SectionTitle id="schedule-title">Backup schedule</SectionTitle>
      <dl className="panel px-5">
        {rows.map(([k, v, note]) => (
          <div key={k} className="flex items-baseline justify-between gap-4 border-b border-rule py-3 last:border-b-0">
            <dt className="text-muted">{k}</dt>
            <dd className="m-0 text-right">
              <span className="num font-medium text-ink">{v}</span>
              <span className="block text-[12px] text-muted">{note}</span>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function RecentActivity({ events }: { events: ActivityEvent[] }) {
  const { prefs } = usePrefs()
  return (
    <section aria-labelledby="recent-title">
      <SectionTitle id="recent-title">Recent activity</SectionTitle>
      <div className="panel px-5">
        <ul>
          {events.map((e) => (
            <li key={e.id} className="flex items-start gap-3 border-b border-rule py-3 last:border-b-0">
              <span className="pt-1.5">
                <SeverityDot severity={e.severity} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="truncate text-ink">{e.title}</span>
                  <span className="num shrink-0 text-[12px] text-muted">{f.time(e.at, prefs.timeZone)}</span>
                </div>
                <p className="mt-0.5 line-clamp-2 text-[13px] leading-[18px] text-muted">{e.detail}</p>
              </div>
            </li>
          ))}
        </ul>
        <div className="border-t border-rule py-3">
          <Link to="/activity" className="btn btn-text">
            View all activity
          </Link>
        </div>
      </div>
    </section>
  )
}

function OverviewSkeleton() {
  return (
    <Loading label="overview">
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex flex-col gap-6">
          <div className="panel p-6">
            <Skeleton w={260} />
            <Skeleton w={140} h={36} className="mt-2" />
            <Skeleton w="70%" className="mt-2" />
            <Skeleton w="100%" h={86} className="mt-6" />
          </div>
          <div className="panel h-[106px]" />
          <div className="panel h-[170px]" />
        </div>
        <div className="panel h-[380px]" />
      </div>
    </Loading>
  )
}
