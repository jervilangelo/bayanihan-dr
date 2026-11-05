import { Check, Circle, LoaderCircle, Minus, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { PageHeader, SectionTitle, Skeleton } from '../components/ui'
import {
  ACTIVE_STATUSES,
  RunnerError,
  createRunnerClient,
  getToken,
  setToken,
  type JobStep,
  type OffsitePoint,
  type RunnerJob,
} from '../data/runner-client'
import { usePrefs } from '../lib/context'
import * as f from '../lib/format'

const client = createRunnerClient(`${import.meta.env.BASE_URL}__runner`)
const POLL_MS = 3000

/**
 * Local operations mode: real recovery drills through the authenticated job runner (Phase 6).
 * Every drill stops for an explicit, typed approval before Terraform creates anything.
 */
export function OpsRecoveryPage() {
  const [token, setTok] = useState(getToken())
  const [identity, setIdentity] = useState<string | null>(null)
  const [error, setError] = useState<RunnerError | null>(null)
  const [points, setPoints] = useState<OffsitePoint[] | null>(null)
  const [jobs, setJobs] = useState<RunnerJob[] | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [s, js] = await Promise.all([client.session(), client.jobs()])
      setIdentity(s.identity)
      setJobs(js)
      setError(null)
    } catch (e) {
      setError(e instanceof RunnerError ? e : new RunnerError(0, 'error', String(e)))
    }
  }, [])

  useEffect(() => {
    if (!token) return
    void refresh()
    client.recoveryPoints().then(setPoints, () => setPoints([]))
  }, [token, refresh])

  const current = jobs?.[0] ?? null
  const lastDrill = jobs?.find((j) => j.type === 'recovery-drill' && j.status === 'succeeded') ?? null
  const active = current && ACTIVE_STATUSES.includes(current.status) ? current : null

  useEffect(() => {
    if (!active) return
    const t = window.setInterval(() => void refresh(), POLL_MS)
    return () => window.clearInterval(t)
  }, [active, refresh])

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    try {
      await fn()
      await refresh()
    } catch (e) {
      setError(e instanceof RunnerError ? e : new RunnerError(0, 'error', String(e)))
    } finally {
      setBusy(false)
    }
  }

  if (!token || error?.status === 401) {
    return (
      <Frame>
        <TokenForm
          invalid={error?.status === 401 && Boolean(token)}
          onSave={(t) => {
            setToken(t)
            setError(null)
            setTok(t)
          }}
        />
      </Frame>
    )
  }

  return (
    <Frame identity={identity}>
      {error && error.status !== 401 && (
        <p role="alert" className="rounded-lg bg-neg-bg px-4 py-3 text-[13px] text-neg-ink">
          {error.message}
        </p>
      )}
      {!jobs && !error && (
        <div className="panel p-6">
          <Skeleton w={220} />
          <Skeleton w="60%" className="mt-4" />
        </div>
      )}
      {jobs && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="flex min-w-0 flex-col gap-6">
            {current ? <JobPanel job={current} busy={busy} act={act} /> : <NoJobsYet />}
            {lastDrill && lastDrill.id !== current?.id && (
              <section className="panel flex flex-col gap-3 p-6" aria-labelledby="last-drill-title">
                <div className="flex flex-wrap items-baseline gap-3">
                  <h2 id="last-drill-title" className="text-[18px] leading-6 font-semibold">
                    Last verified drill
                  </h2>
                  <code className="ml-auto font-mono text-[12px] text-muted">{lastDrill.id}</code>
                </div>
                <Result job={lastDrill} />
              </section>
            )}
          </div>
          <aside className="flex flex-col gap-6">
            <StartDrill points={points} disabled={Boolean(active) || busy} onStart={(id) => act(() => client.startDrill(id))} />
            <Teardown disabled={Boolean(active) || busy} onStart={() => act(() => client.startTeardown())} />
          </aside>
        </div>
      )}
    </Frame>
  )
}

function Frame({ children, identity }: { children: ReactNode; identity?: string | null }) {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Recovery"
        subline="Real recovery drills into AWS, through the local job runner. Each drill is planned first and only runs after an administrator approves the exact plan."
        action={
          identity ? (
            <span className="rounded-full bg-tint px-3 py-1 text-[12px] font-medium text-accent-ink">Signed in · {identity.replace(/^AWSReservedSSO_|_[0-9a-f]+$/g, '')}</span>
          ) : undefined
        }
      />
      {children}
    </div>
  )
}

function TokenForm({ onSave, invalid }: { onSave: (t: string) => void; invalid: boolean }) {
  const [value, setValue] = useState('')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (value.trim()) onSave(value)
  }
  return (
    <form onSubmit={submit} className="panel flex max-w-[560px] flex-col gap-3 p-6" aria-labelledby="token-title">
      <h2 id="token-title" className="text-[18px] leading-6 font-semibold">
        Administrator sign-in
      </h2>
      <p className="text-[14px] leading-[22px] text-muted">
        Start the job runner (<code className="font-mono text-[13px]">python -m bdr_runner</code> in <code className="font-mono text-[13px]">backend/</code>), then paste the token
        from <code className="font-mono text-[13px]">backend/var/admin-token</code>. It is kept only for this browser tab.
      </p>
      <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink">
        Administrator token
        <input
          type="password"
          autoComplete="off"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="h-10 rounded-lg border border-control bg-surface px-3 font-mono text-[13px]"
          aria-invalid={invalid}
        />
      </label>
      {invalid && (
        <p role="alert" className="text-[13px] text-neg-ink">
          That token was not accepted.
        </p>
      )}
      <button type="submit" className="btn btn-primary self-start" disabled={!value.trim()}>
        Sign in
      </button>
    </form>
  )
}

function NoJobsYet() {
  return (
    <section className="panel flex flex-col gap-2 p-6">
      <h2 className="text-[18px] leading-6 font-semibold">No recovery jobs yet</h2>
      <p className="max-w-[60ch] text-[14px] leading-[22px] text-muted">
        Choose an off-site recovery point and prepare a drill. Terraform plans the recovery environment first; nothing is created until you approve
        that plan.
      </p>
    </section>
  )
}

function StartDrill({ points, disabled, onStart }: { points: OffsitePoint[] | null; disabled: boolean; onStart: (id: string) => void }) {
  const { prefs } = usePrefs()
  const [selected, setSelected] = useState<string | null>(null)
  const chosen = selected ?? points?.[0]?.id ?? null
  return (
    <section className="panel flex flex-col gap-3 p-5" aria-labelledby="start-title">
      <h2 id="start-title" className="text-[16px] leading-6 font-semibold">
        Prepare a recovery drill
      </h2>
      <p className="text-[13px] leading-5 text-muted">Off-site recovery points (verified backups in S3). Recovery never depends on the office server.</p>
      {points === null && <Skeleton w="80%" />}
      {points?.length === 0 && <p className="text-[13px] text-neg-ink">No verified off-site backups. Upload one first (backend README).</p>}
      <fieldset className="flex flex-col gap-1.5" disabled={disabled}>
        <legend className="sr-only">Recovery point</legend>
        {points?.slice(0, 6).map((p) => (
          <label key={p.id} className="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 text-[13px] hover:bg-raised">
            <input type="radio" name="point" className="accent-[var(--color-accent)]" checked={chosen === p.id} onChange={() => setSelected(p.id)} />
            <span className="num text-ink">{f.dateTime(p.scheduledAt, prefs.timeZone)}</span>
            <span className="ml-auto text-muted">{f.count(p.records.farmers ?? 0)} members</span>
          </label>
        ))}
      </fieldset>
      <button type="button" className="btn btn-primary" disabled={disabled || !chosen} onClick={() => chosen && onStart(chosen)}>
        Prepare drill (plan only)
      </button>
    </section>
  )
}

function Teardown({ disabled, onStart }: { disabled: boolean; onStart: () => void }) {
  return (
    <section className="panel flex flex-col gap-3 p-5" aria-labelledby="teardown-title">
      <h2 id="teardown-title" className="text-[16px] leading-6 font-semibold">
        Remove the recovery environment
      </h2>
      <p className="text-[13px] leading-5 text-muted">
        Plans the removal of the recovery host and network so they stop costing money. Backups, IAM and the budget are not touched. Also needs
        approval.
      </p>
      <button type="button" className="btn btn-secondary" disabled={disabled} onClick={onStart}>
        Prepare teardown (plan only)
      </button>
    </section>
  )
}

const STATUS_LABEL: Record<RunnerJob['status'], { label: string; cls: string }> = {
  preparing: { label: 'Preparing', cls: 'bg-sky-tint text-sky-ink' },
  'awaiting-approval': { label: 'Awaiting approval', cls: 'bg-warn-bg text-warn-ink' },
  applying: { label: 'Applying', cls: 'bg-sky-tint text-sky-ink' },
  restoring: { label: 'Restoring', cls: 'bg-sky-tint text-sky-ink' },
  succeeded: { label: 'Succeeded', cls: 'bg-tint text-accent-ink' },
  failed: { label: 'Failed', cls: 'bg-neg-bg text-neg-ink' },
  cancelled: { label: 'Cancelled', cls: 'bg-raised text-muted' },
}

function JobPanel({ job, busy, act }: { job: RunnerJob; busy: boolean; act: (fn: () => Promise<unknown>) => void }) {
  const s = STATUS_LABEL[job.status]
  return (
    <section className="panel flex flex-col gap-5 p-6" aria-labelledby="job-title" aria-live="polite">
      <div className="flex flex-wrap items-baseline gap-3">
        <h2 id="job-title" className="text-[18px] leading-6 font-semibold">
          {job.type === 'recovery-drill' ? 'Recovery drill' : 'Teardown'}
        </h2>
        <span className={`rounded-full px-2.5 py-0.5 text-[12px] font-medium ${s.cls}`}>{s.label}</span>
        <code className="ml-auto font-mono text-[12px] text-muted">{job.id}</code>
      </div>
      {job.error && (
        <p role="alert" className="rounded-lg bg-neg-bg px-4 py-3 text-[13px] leading-5 text-neg-ink">
          {job.error}
        </p>
      )}
      <AnimatePresence initial={false}>
        {job.status === 'awaiting-approval' && job.plan && (
          <motion.div key="approve" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
            <Approval job={job} busy={busy} act={act} />
          </motion.div>
        )}
      </AnimatePresence>
      {job.type === 'recovery-drill' && job.status === 'succeeded' && <Result job={job} />}
      <Timeline steps={job.steps} />
    </section>
  )
}

function Approval({ job, busy, act }: { job: RunnerJob; busy: boolean; act: (fn: () => Promise<unknown>) => void }) {
  const [typed, setTyped] = useState('')
  const plan = job.plan!
  const c = plan.counts
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-warn-border bg-warn-bg p-4">
      <p className="text-[14px] leading-[22px] text-warn-ink">
        <span className="font-semibold">Review before approving.</span> Terraform will {c.create ? `create ${c.create}` : ''}
        {c.delete ? `remove ${c.delete}` : ''} resource{c.create + c.delete === 1 ? '' : 's'}; nothing else changes.
        {job.type === 'recovery-drill' && ` Estimated cost while running: about USD ${plan.hourly_cost_usd.toFixed(3)} per hour.`}
      </p>
      <details className="text-[13px] text-ink">
        <summary className="cursor-pointer text-warn-ink">Show the {plan.resources.length} planned changes</summary>
        <ul className="mt-2 flex flex-col gap-0.5 font-mono text-[12px]">
          {plan.resources.map((r) => (
            <li key={r.address}>
              {r.action === 'create' ? '+' : '−'} {r.address}
            </li>
          ))}
        </ul>
      </details>
      <label className="flex flex-col gap-1.5 text-[13px] font-medium text-warn-ink">
        Type the job ID to approve
        <input value={typed} onChange={(e) => setTyped(e.target.value)} className="h-10 rounded-lg border border-control bg-surface px-3 font-mono text-[13px] text-ink" placeholder={job.id} />
      </label>
      <div className="flex flex-wrap gap-3">
        <button type="button" className="btn btn-primary" disabled={busy || typed.trim() !== job.id} onClick={() => act(() => client.approve(job.id, typed.trim()))}>
          Approve and {job.type === 'recovery-drill' ? 'start recovery' : 'remove'}
        </button>
        <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => act(() => client.cancel(job.id))}>
          Cancel
        </button>
      </div>
    </div>
  )
}

function Result({ job }: { job: RunnerJob }) {
  const r = job.result!
  const { prefs } = usePrefs()
  const rows = useMemo(
    () => [
      ['Recovery time (RTO)', `${f.clock(Math.round(r.rto_seconds ?? 0))}`, `target ${Math.round((r.rto_target_seconds ?? 0) / 60)} min`, r.within_rto],
      ['Data-loss window (RPO)', `${f.clock(Math.round(r.rpo_seconds ?? 0))}`, `target ${Math.round((r.rpo_target_seconds ?? 0) / 60)} min`, r.within_rpo],
    ] as const,
    [r],
  )
  return (
    <div className="flex flex-col gap-3 rounded-lg bg-tint p-4">
      <p className="text-[14px] font-semibold text-accent-ink">
        Measured, not simulated. CMS recovered at {r.recovered_at ? f.dateTime(r.recovered_at, prefs.timeZone) : '—'} and verified against the backup manifest.
      </p>
      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {rows.map(([k, v, target, ok]) => (
          <div key={k} className="rounded-lg bg-surface p-3">
            <dt className="text-[12px] text-muted">{k}</dt>
            <dd className="m-0 flex items-baseline gap-2">
              <span className="num text-[22px] font-semibold text-ink">{v}</span>
              <span className={`text-[12px] ${ok ? 'text-accent-ink' : 'text-neg-ink'}`}>
                {ok ? 'within' : 'over'} {target}
              </span>
            </dd>
          </div>
        ))}
      </dl>
      {r.records?.restored && (
        <p className="text-[13px] text-ink">
          Records restored: {Object.entries(r.records.restored).map(([t, n]) => `${t.replace('_', ' ')} ${f.count(n)}`).join(' · ')}
        </p>
      )}
      {job.result?.recovery_point && (
        <p className="text-[12px] text-muted">
          Restored recovery point {job.result.recovery_point.id}; {job.result.approval_wait_seconds != null && `approval took ${f.clock(Math.round(job.result.approval_wait_seconds))}, `}
          provisioning {f.clock(Math.round(job.result.provision_seconds ?? 0))}, host restore {f.clock(Math.round(job.result.host_seconds ?? 0))}.
        </p>
      )}
    </div>
  )
}

const ICON: Record<JobStep['status'], ReactNode> = {
  ok: <Check className="size-4 text-accent" aria-hidden="true" />,
  running: <LoaderCircle className="size-4 animate-spin text-sky motion-reduce:animate-none" aria-hidden="true" />,
  failed: <X className="size-4 text-neg" aria-hidden="true" />,
  skipped: <Minus className="size-4 text-muted" aria-hidden="true" />,
  pending: <Circle className="size-4 text-control" aria-hidden="true" />,
}

function Timeline({ steps }: { steps: JobStep[] }) {
  const { prefs } = usePrefs()
  return (
    <div>
      <SectionTitle>Steps</SectionTitle>
      <ol className="flex flex-col">
        {steps.map((s) => (
          <li key={s.id} className="flex gap-3 border-t border-rule py-2.5 first:border-t-0">
            <span className="pt-0.5">{ICON[s.status]}</span>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-3">
                <span className={s.status === 'pending' ? 'text-muted' : 'text-ink'}>
                  {s.title}
                  <span className="sr-only"> ({s.status})</span>
                </span>
                <span className="num shrink-0 text-[12px] text-muted">
                  {s.finished_at ? f.time(s.finished_at, prefs.timeZone) : s.started_at ? f.time(s.started_at, prefs.timeZone) : ''}
                </span>
              </div>
              {s.detail && <p className="mt-0.5 text-[13px] leading-[18px] break-words text-muted">{s.detail}</p>}
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
