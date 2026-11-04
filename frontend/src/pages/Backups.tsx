import { ChevronDown } from 'lucide-react'
import { Fragment, useState } from 'react'
import { Link } from 'react-router'
import { BackupPill, BlockError, Loading, PageHeader, Skeleton, Stagger, StaggerItem } from '../components/ui'
import type { Backup, DashboardProvider } from '../data/types'
import { useProvider, usePrefs, useResource } from '../lib/context'
import * as f from '../lib/format'

type Tab = 'all' | 'points' | 'problems'
const loadBackups = (p: DashboardProvider) => p.listBackups()
const PAGE = 24

export function BackupsPage() {
  const res = useResource(loadBackups)
  const demo = useProvider().mode === 'demo'
  const [tab, setTab] = useState<Tab>('all')
  const [shown, setShown] = useState(PAGE)
  const all = res.data ?? []
  const points = all.filter((b) => b.status === 'verified')
  const problems = all.filter((b) => b.status === 'failed' || b.status === 'missed')
  const rows = tab === 'all' ? all : tab === 'points' ? points : problems
  const tabs: { id: Tab; label: string; n: number }[] = [
    { id: 'all', label: 'All backups', n: all.length },
    { id: 'points', label: 'Recovery points', n: points.length },
    { id: 'problems', label: 'Problems', n: problems.length },
  ]

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Backups"
        subline={
          res.data
            ? `${all.length} ${demo ? 'hourly backups in the last 72 hours' : 'backups kept on this computer'}. ${points.length} passed both the checksum and a test restore and can be used to recover.`
            : 'Loading the backup history…'
        }
      />

      <div role="tablist" aria-label="Backup filter" className="flex gap-6 overflow-x-auto border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={tab === t.id}
            onClick={() => {
              setTab(t.id)
              setShown(PAGE)
            }}
            className={`-mb-px flex h-11 shrink-0 items-center gap-2 border-b-2 text-[14px] transition-colors duration-150 ${
              tab === t.id ? 'border-ink font-medium text-ink' : 'border-transparent text-muted hover:text-ink'
            }`}
          >
            {t.label}
            <span className="num text-[13px] text-muted">{res.data ? t.n : ''}</span>
          </button>
        ))}
      </div>

      {res.error && <BlockError what="backups" onRetry={res.retry} />}
      {res.loading && <TableSkeleton />}
      {res.data && (
        <section aria-label="Backup history">
          <div className="mb-2 flex items-center justify-between text-[13px] text-muted">
            <span className="num">
              {Math.min(shown, rows.length)} of {rows.length} shown
            </span>
            <span>Newest first</span>
          </div>
          {rows.length === 0 ? (
            <p className="rounded-lg border border-dashed border-control px-4 py-3 text-muted">No backups in this view.</p>
          ) : (
            <BackupTable rows={rows.slice(0, shown)} />
          )}
          {shown < rows.length && (
            <button type="button" className="btn btn-secondary mt-4 w-full sm:w-auto" onClick={() => setShown((n) => n + PAGE)}>
              Show {Math.min(PAGE, rows.length - shown)} more
            </button>
          )}
        </section>
      )}
    </div>
  )
}

function BackupTable({ rows }: { rows: Backup[] }) {
  const { prefs } = usePrefs()
  const [open, setOpen] = useState<string | null>(null)

  return (
    <Stagger>
      {/* desktop and tablet: a real table */}
      <table className="hidden w-full border-collapse text-left md:table">
        <thead>
          <tr className="text-[12px] text-muted">
            <th className="h-9 py-0 pr-4 font-normal">Scheduled ({f.zoneLabel(prefs.timeZone)})</th>
            <th className="py-0 pr-4 font-normal">Status</th>
            <th className="py-0 pr-4 text-right font-normal">Size</th>
            <th className="py-0 pr-4 text-right font-normal">Ledger entries</th>
            <th className="hidden py-0 pr-4 font-normal lg:table-cell">Checksum</th>
            <th className="py-0 text-right font-normal">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((b) => {
            const isOpen = open === b.id
            return (
              <Fragment key={b.id}>
                <tr className="border-t border-rule transition-colors duration-150 hover:bg-surface">
                  <td className="h-12 pr-4">
                    <button
                      type="button"
                      className="flex items-center gap-2 text-left text-ink"
                      aria-expanded={isOpen}
                      aria-controls={`manifest-${b.id}`}
                      onClick={() => setOpen(isOpen ? null : b.id)}
                    >
                      <ChevronDown
                        size={14}
                        aria-hidden="true"
                        className={`text-muted transition-transform duration-150 ${isOpen ? 'rotate-180' : ''}`}
                      />
                      <span className="num">{f.dateTime(b.scheduledAt, prefs.timeZone)}</span>
                    </button>
                  </td>
                  <td className="pr-4">
                    <BackupPill status={b.status} />
                  </td>
                  <td className="num pr-4 text-right text-ink">{f.bytes(b.sizeBytes)}</td>
                  <td className="num pr-4 text-right text-ink">{b.records ? f.count(b.records.transactions) : <span className="text-muted">—</span>}</td>
                  <td className="hidden pr-4 font-mono text-[13px] text-muted lg:table-cell">{f.shortHash(b.sha256)}</td>
                  <td className="text-right">
                    {b.status === 'verified' ? (
                      <Link to={`/recovery?point=${b.id}`} className="btn btn-text">
                        Recover to this point
                      </Link>
                    ) : (
                      <span className="text-[13px] text-muted">Not recoverable</span>
                    )}
                  </td>
                </tr>
                {isOpen && (
                  <tr id={`manifest-${b.id}`}>
                    <td colSpan={6} className="pb-4">
                      <Manifest b={b} />
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>

      {/* phone: two-line rows */}
      <ul className="md:hidden">
        {rows.map((b) => {
          const isOpen = open === b.id
          return (
            <StaggerItem key={b.id} as="li" className="border-t border-rule py-3">
                <button
                  type="button"
                  className="flex min-h-11 w-full items-center justify-between gap-3 text-left"
                  aria-expanded={isOpen}
                  onClick={() => setOpen(isOpen ? null : b.id)}
                >
                  <span>
                    <span className="num block text-ink">{f.dateTime(b.scheduledAt, prefs.timeZone)}</span>
                    <span className="num block text-[13px] text-muted">
                      {f.bytes(b.sizeBytes)}
                      {b.records ? ` · ${f.count(b.records.transactions)} ledger entries` : ''}
                    </span>
                  </span>
                  <BackupPill status={b.status} />
                </button>
                {isOpen && (
                  <div className="mt-2">
                    <Manifest b={b} />
                  </div>
                )}
                {b.status === 'verified' && (
                  <Link to={`/recovery?point=${b.id}`} className="btn btn-text mt-1 inline-flex min-h-11">
                    Recover to this point
                  </Link>
                )}
            </StaggerItem>
          )
        })}
      </ul>
    </Stagger>
  )
}

function Manifest({ b }: { b: Backup }) {
  const { prefs } = usePrefs()
  const provider = useProvider()
  const rows: [string, string][] = [
    ['Backup ID', b.id],
    ['Completed', b.completedAt ? f.dateTime(b.completedAt, prefs.timeZone) : '—'],
    ['SHA-256', b.sha256 ?? '—'],
    ['Checksum', { match: 'Matches the manifest', mismatch: 'Does not match the manifest', 'not-run': 'Not run' }[b.checksum]],
    ['Test restore', { passed: 'Passed', failed: 'Failed', 'not-run': 'Not run' }[b.restoreTest]],
    ['Off-site copy', { stored: 'Stored', rejected: 'Rejected', 'not-stored': 'Not stored' }[b.offsite]],
    ['Schema revision', b.schemaRevision],
  ]
  if (b.records) {
    rows.push(['Members', f.count(b.records.farmers)], ['Inventory items', f.count(b.records.inventoryItems)], ['Ledger entries', f.count(b.records.transactions)])
  }
  return (
    <div className="rounded-lg bg-raised p-4">
      {b.failureReason && <p className="mb-3 text-ink">{b.failureReason}</p>}
      <dl className="grid grid-cols-1 gap-x-8 gap-y-1.5 text-[13px] sm:grid-cols-[140px_1fr]">
        {rows.map(([k, v]) => (
          <Fragment key={k}>
            <dt className="text-muted">{k}</dt>
            <dd className={`m-0 break-all text-ink ${k === 'SHA-256' || k === 'Backup ID' ? 'font-mono text-[12px]' : 'num'}`}>{v}</dd>
          </Fragment>
        ))}
      </dl>
      {b.checks && b.checks.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1 border-t border-rule pt-3 text-[13px]" aria-label="Verification checks">
          {b.checks.map((c) => (
            <li key={c.name} className="flex gap-2">
              <span className={c.ok ? 'text-accent-ink' : 'text-neg-ink'} aria-hidden="true">{c.ok ? '✓' : '✕'}</span>
              <span className="text-ink">
                <span className="sr-only">{c.ok ? 'Passed: ' : 'Failed: '}</span>
                {c.detail}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-[12px] text-muted">
        {provider.mode === 'demo' ? 'Sample manifest from the demo dataset, not a real backup.' : 'Manifest written by the local backup engine.'}
      </p>
    </div>
  )
}

function TableSkeleton() {
  return (
    <Loading label="backups">
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className="flex h-12 items-center gap-6 border-t border-rule">
          <Skeleton w={140} />
          <Skeleton w={64} h={22} />
          <Skeleton w={70} className="ml-auto" />
          <Skeleton w={60} />
        </div>
      ))}
    </Loading>
  )
}
