import { Fragment, useMemo, useState } from 'react'
import { BlockError, Loading, PageHeader, SeverityDot, SimulatedTag, Skeleton } from '../components/ui'
import type { ActivityCategory, ActivityEvent, DashboardProvider } from '../data/types'
import { usePrefs, useResource } from '../lib/context'
import * as f from '../lib/format'

type Filter = 'all' | ActivityCategory
const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'backup', label: 'Backups' },
  { id: 'recovery', label: 'Recovery' },
  { id: 'infrastructure', label: 'Infrastructure' },
  { id: 'audit', label: 'Audit' },
]
const PAGE = 40
const loadActivity = (p: DashboardProvider) => p.listActivity()

export function ActivityPage() {
  const res = useResource(loadActivity)
  const { prefs } = usePrefs()
  const [filter, setFilter] = useState<Filter>('all')
  const [problemsOnly, setProblemsOnly] = useState(false)
  const [shown, setShown] = useState(PAGE)

  const events = useMemo(
    () => (res.data ?? []).filter((e) => (filter === 'all' || e.category === filter) && (!problemsOnly || e.severity !== 'info')),
    [res.data, filter, problemsOnly],
  )
  const counts = useMemo(() => {
    const c: Record<Filter, number> = { all: 0, backup: 0, recovery: 0, infrastructure: 0, audit: 0 }
    for (const e of res.data ?? []) {
      if (problemsOnly && e.severity === 'info') continue
      c.all++
      c[e.category]++
    }
    return c
  }, [res.data, problemsOnly])

  const groups = useMemo(() => {
    const g = new Map<string, ActivityEvent[]>()
    for (const e of events.slice(0, shown)) {
      const key = f.day(e.at, prefs.timeZone)
      g.set(key, [...(g.get(key) ?? []), e])
    }
    return [...g.entries()]
  }, [events, shown, prefs.timeZone])

  const problems = (res.data ?? []).filter((e) => e.severity !== 'info').length

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Activity"
        subline={
          res.data
            ? `Every backup, recovery, infrastructure and audit event, newest first. ${problems} warnings and errors in the last 72 hours.`
            : 'Loading the activity log…'
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div role="tablist" aria-label="Event type" className="flex gap-5 overflow-x-auto border-b border-border sm:flex-1">
          {FILTERS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={filter === t.id}
              onClick={() => {
                setFilter(t.id)
                setShown(PAGE)
              }}
              className={`-mb-px flex h-11 shrink-0 items-center gap-2 border-b-2 text-[14px] transition-colors duration-150 ${
                filter === t.id ? 'border-ink font-medium text-ink' : 'border-transparent text-muted hover:text-ink'
              }`}
            >
              {t.label}
              <span className="num text-[13px] text-muted">{res.data ? counts[t.id] : ''}</span>
            </button>
          ))}
        </div>
        <label className="flex min-h-11 cursor-pointer items-center gap-2 text-[14px] text-ink sm:pl-6">
          <input type="checkbox" className="size-4 accent-[var(--color-accent)]" checked={problemsOnly} onChange={(e) => setProblemsOnly(e.target.checked)} />
          Warnings and errors only
        </label>
      </div>

      {res.error && <BlockError what="activity" onRetry={res.retry} />}
      {res.loading && (
        <Loading label="activity">
          {Array.from({ length: 8 }, (_, i) => (
            <div key={i} className="flex h-14 items-center gap-4 border-t border-rule">
              <Skeleton w={44} />
              <Skeleton w={220} />
              <Skeleton w={120} className="ml-auto" />
            </div>
          ))}
        </Loading>
      )}

      {res.data && (
        <section aria-label="Events">
          {events.length === 0 && (
            <p className="rounded-lg border border-dashed border-control px-4 py-3 text-muted">
              {filter === 'recovery'
                ? 'No recoveries yet. Run a simulation from the Recovery page and it will be logged here.'
                : 'No events match this filter.'}
            </p>
          )}
          {groups.map(([dayLabel, list]) => (
            <Fragment key={dayLabel}>
              <h2 className="mt-6 mb-2 text-[14px] font-semibold text-ink first:mt-0">{dayLabel}</h2>
              <ol className="panel px-4 sm:px-5">
                {list.map((e) => (
                  <li key={e.id} className="grid grid-cols-[44px_14px_1fr] gap-x-3 border-b border-rule py-3 last:border-b-0 sm:grid-cols-[52px_14px_1fr_auto]">
                    <time dateTime={e.at} className="num pt-px text-[13px] text-muted">
                      {f.time(e.at, prefs.timeZone)}
                    </time>
                    <span className="pt-1.5">
                      <SeverityDot severity={e.severity} />
                    </span>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 text-ink">
                        {e.title}
                        {e.category === 'recovery' && <SimulatedTag />}
                      </div>
                      <p className="mt-0.5 text-[13px] leading-[18px] text-muted">{e.detail}</p>
                      <p className="mt-1 text-[12px] text-muted sm:hidden">{e.actor}</p>
                    </div>
                    <span className="hidden pt-px text-right text-[13px] text-muted sm:block">{e.actor}</span>
                  </li>
                ))}
              </ol>
            </Fragment>
          ))}
          {shown < events.length && (
            <button type="button" className="btn btn-secondary mt-4 w-full sm:w-auto" onClick={() => setShown((n) => n + PAGE)}>
              Show older events ({f.count(events.length - shown)} more)
            </button>
          )}
        </section>
      )}
    </div>
  )
}
