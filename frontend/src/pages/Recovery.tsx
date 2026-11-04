import { Check, Circle, Minus } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { BlockError, Loading, PageHeader, SectionTitle, SimulatedTag, Skeleton, Stagger, StaggerItem } from '../components/ui'
import { RECOVERY_STEPS, TOTAL_SIMULATED_SECONDS } from '../data/simulation'
import { ProviderError, type Backup, type DashboardProvider, type RecoveryState } from '../data/types'
import { usePrefs, useProvider, useResource } from '../lib/context'
import * as f from '../lib/format'

const loadRecoveryContext = (p: DashboardProvider) => Promise.all([p.getOverview(), p.listBackups(), p.activeRecovery()])
const POINTS_SHOWN = 8

export function RecoveryPage() {
  const provider = useProvider()
  const res = useResource(loadRecoveryContext)
  const [params] = useSearchParams()
  const [selected, setSelected] = useState<string | null>(null)
  const [acknowledged, setAcknowledged] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [state, setState] = useState<RecoveryState | null>(null)
  const [startError, setStartError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const confirmRef = useRef<HTMLDialogElement>(null)

  const [overview, backups, active] = res.data ?? [null, null, null]

  // Default selection: a point passed from the Backups page, else the newest verified point.
  useEffect(() => {
    if (!backups || selected) return
    const fromLink = params.get('point')
    const valid = backups.find((b) => b.id === fromLink && b.status === 'verified')
    setSelected(valid?.id ?? backups.find((b) => b.status === 'verified')?.id ?? null)
  }, [backups, params, selected])

  // Resume watching a simulation that is still running (e.g. after navigating away and back).
  useEffect(() => {
    if (active && !jobId) setJobId(active.id)
  }, [active, jobId])

  // Poll the provider while a job runs.
  useEffect(() => {
    if (!jobId) return
    let alive = true
    const tick = async () => {
      const s = await provider.getRecoveryState(jobId)
      if (!alive) return
      setState(s)
      if (s.status === 'running') timer = window.setTimeout(tick, 150)
    }
    let timer = window.setTimeout(tick, 0)
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [jobId, provider])

  const start = useCallback(async () => {
    if (!selected) return
    setStarting(true)
    setStartError(null)
    try {
      const job = await provider.startRecovery(selected)
      setJobId(job.id)
      confirmRef.current?.close()
    } catch (e) {
      setStartError(e instanceof ProviderError ? e.message : 'The simulation could not start.')
      confirmRef.current?.close()
    } finally {
      setStarting(false)
    }
  }, [provider, selected])

  const reset = () => {
    setJobId(null)
    setState(null)
    setAcknowledged(false)
    res.retry()
  }

  const point = backups?.find((b) => b.id === (state?.backupId ?? selected)) ?? null
  const phase: 'plan' | 'running' | 'done' = !jobId ? 'plan' : !state || state.status === 'running' ? 'running' : 'done'

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Recovery"
        subline="Practise the steps the cooperative would follow if the office server were lost. In this demo the recovery is a simulation: nothing connects to AWS or Terraform."
        action={<SimulatedTag>Simulation</SimulatedTag>}
      />

      {res.error && <BlockError what="the recovery plan" onRetry={res.retry} />}
      {res.loading && !res.data && (
        <Loading label="recovery plan">
          <div className="panel h-[420px] p-6">
            <Skeleton w={220} />
            <Skeleton w="60%" className="mt-4" />
          </div>
        </Loading>
      )}

      {overview && backups && (
        <AnimatePresence mode="wait" initial={false}>
          {phase === 'plan' && (
            <motion.div key="plan" exit={{ opacity: 0, transition: { duration: 0.12 } }}>
              <Stagger className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
                <div className="flex min-w-0 flex-col gap-6">
                  <StaggerItem>
                    <Preflight backups={backups} point={point} running={Boolean(active)} />
                  </StaggerItem>
                  <StaggerItem>
                    <PointPicker backups={backups} selected={selected} onSelect={setSelected} now={overview.generatedAt} />
                  </StaggerItem>
                  <StaggerItem>
                    <PlanSteps />
                  </StaggerItem>
                </div>
                <StaggerItem>
                  <aside className="panel flex flex-col gap-4 p-5 xl:sticky xl:top-8" aria-labelledby="approve-title">
                    <h2 id="approve-title" className="text-[18px] leading-6 font-semibold">
                      Recovery plan
                    </h2>
                    <PlanSummary point={point} now={overview.generatedAt} rto={overview.targets.rtoMinutes} rpo={overview.targets.rpoMinutes} />
                    <label className="flex cursor-pointer items-start gap-3 rounded-lg bg-raised p-3 text-[13px] leading-5">
                      <input
                        type="checkbox"
                        className="mt-0.5 size-4 accent-[var(--color-accent)]"
                        checked={acknowledged}
                        onChange={(e) => setAcknowledged(e.target.checked)}
                      />
                      <span>I understand this is a simulation. It creates no AWS resources and the timings are illustrative.</span>
                    </label>
                    {startError && (
                      <p role="alert" className="rounded-lg bg-neg-bg px-3 py-2 text-[13px] text-neg-ink">
                        {startError}
                      </p>
                    )}
                    <button
                      type="button"
                      className="btn btn-primary w-full"
                      disabled={!acknowledged || !point}
                      onClick={() => confirmRef.current?.showModal()}
                    >
                      Review and approve
                    </button>
                    {!acknowledged && <p className="text-[12px] text-muted">Tick the box above to enable approval.</p>}
                  </aside>
                </StaggerItem>
              </Stagger>
            </motion.div>
          )}

          {phase !== 'plan' && (
            <motion.div key="run" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
              <Progress
                state={state}
                point={point}
                onStop={() => jobId && provider.cancelRecovery(jobId)}
                onReset={reset}
              />
            </motion.div>
          )}
        </AnimatePresence>
      )}

      <dialog
        ref={confirmRef}
        aria-labelledby="confirm-title"
        className="m-auto w-[min(440px,calc(100vw-32px))] rounded-xl border border-border bg-surface p-6 text-ink shadow-[0_12px_32px_rgba(38,59,54,0.16)] backdrop:bg-ink/25"
      >
        <h2 id="confirm-title" className="text-[18px] leading-6 font-semibold">
          Start the simulated recovery?
        </h2>
        {point && overview && (
          <p className="mt-2 text-muted">
            Restore from the backup of <span className="font-medium text-ink">{f.dateTime(point.scheduledAt)}</span>. In a real
            recovery this step creates billable AWS resources; here it only plays the steps back.
          </p>
        )}
        <div className="mt-6 flex justify-end gap-2">
          <button type="button" className="btn btn-secondary" onClick={() => confirmRef.current?.close()}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" disabled={starting} onClick={start}>
            {starting ? 'Starting…' : 'Approve and start'}
          </button>
        </div>
      </dialog>
    </div>
  )
}

function Preflight({ backups, point, running }: { backups: Backup[]; point: Backup | null; running: boolean }) {
  const hasPoint = backups.some((b) => b.status === 'verified')
  const items: { label: string; ok: boolean; note: string; simulated?: boolean }[] = [
    { label: 'A verified recovery point exists', ok: hasPoint, note: hasPoint ? 'Checksum matched and test-restored' : 'No backup has passed verification' },
    { label: 'Its copy is stored off-site', ok: point?.offsite === 'stored', note: point?.offsite === 'stored' ? 'Encrypted object storage, away from the office' : 'Choose a stored point' },
    { label: 'Recovery credentials are on this workstation', ok: true, note: 'Kept apart from the office server', simulated: true },
    { label: 'Infrastructure state is reachable', ok: true, note: 'Remote state with locking', simulated: true },
    { label: 'No other recovery is running', ok: !running, note: running ? 'Wait for it to finish' : 'Only one recovery at a time' },
  ]
  return (
    <section className="panel p-5 sm:p-6" aria-labelledby="preflight-title">
      <SectionTitle id="preflight-title" aside={`${items.filter((i) => i.ok).length} of ${items.length} ready`}>
        Before you start
      </SectionTitle>
      <ul className="flex flex-col">
        {items.map((i) => (
          <li key={i.label} className="flex items-start gap-3 border-t border-rule py-3 first:border-t-0 first:pt-0">
            <span className={`mt-0.5 flex size-5 flex-none items-center justify-center rounded-full ${i.ok ? 'bg-tint text-accent' : 'bg-neg-bg text-neg'}`}>
              {i.ok ? <Check size={13} strokeWidth={2.5} aria-hidden="true" /> : <Minus size={13} strokeWidth={2.5} aria-hidden="true" />}
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-ink">
                {i.label}
                <span className="sr-only">{i.ok ? ': ready' : ': not ready'}</span>
              </div>
              <div className="text-[13px] text-muted">
                {i.note}
                {i.simulated && ' · simulated check'}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function PointPicker({ backups, selected, onSelect, now }: { backups: Backup[]; selected: string | null; onSelect: (id: string) => void; now: string }) {
  const { prefs } = usePrefs()
  const recent = backups.slice(0, POINTS_SHOWN)
  return (
    <section className="panel p-5 sm:p-6" aria-labelledby="points-title">
      <SectionTitle id="points-title" aside={<Link to="/backups" className="btn btn-text">All backups</Link>}>
        Choose a recovery point
      </SectionTitle>
      <fieldset>
        <legend className="sr-only">Recovery point</legend>
        <ul className="flex flex-col gap-1">
          {recent.map((b) => {
            const usable = b.status === 'verified'
            const loss = Math.floor((Date.parse(now) - Date.parse(b.scheduledAt)) / 60_000)
            const checked = selected === b.id
            return (
              <li key={b.id}>
                <label
                  className={`flex min-h-12 items-center gap-3 rounded-lg px-3 py-2 transition-colors duration-150 ${
                    !usable ? 'cursor-not-allowed' : checked ? 'cursor-pointer bg-tint-soft outline outline-1 outline-accent' : 'cursor-pointer hover:bg-raised'
                  }`}
                >
                  <input
                    type="radio"
                    name="point"
                    value={b.id}
                    className="size-4 accent-[var(--color-accent)]"
                    disabled={!usable}
                    checked={checked}
                    onChange={() => onSelect(b.id)}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="num block text-ink">{f.dateTime(b.scheduledAt, prefs.timeZone)}</span>
                    <span className="block text-[13px] text-muted">
                      {usable ? `Up to ${f.duration(loss)} of changes would be lost` : b.failureReason}
                    </span>
                  </span>
                  {!usable && <span className="text-[12px] text-muted">Not usable</span>}
                </label>
              </li>
            )
          })}
        </ul>
      </fieldset>
    </section>
  )
}

function PlanSteps() {
  return (
    <section className="panel p-5 sm:p-6" aria-labelledby="steps-title">
      <SectionTitle id="steps-title" aside={`About ${TOTAL_SIMULATED_SECONDS / 60} min, simulated`}>
        What will happen
      </SectionTitle>
      <ol className="flex flex-col">
        {RECOVERY_STEPS.map((s) => (
          <li key={s.id} className="grid grid-cols-[1fr_auto] gap-x-4 border-t border-rule py-2.5 first:border-t-0 first:pt-0">
            <span className="text-ink">{s.title}</span>
            <span className="num text-right text-[13px] text-muted">{f.duration(Math.max(1, Math.round(s.simulatedSeconds / 60)))}</span>
            <span className="col-span-2 text-[13px] text-muted">{s.detail}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}

function PlanSummary({ point, now, rto, rpo }: { point: Backup | null; now: string; rto: number; rpo: number }) {
  const { prefs } = usePrefs()
  const loss = point ? Math.floor((Date.parse(now) - Date.parse(point.scheduledAt)) / 60_000) : null
  const rows: [string, string][] = [
    ['Recovery point', point ? f.dateTime(point.scheduledAt, prefs.timeZone) : '—'],
    ['Changes lost', loss === null ? '—' : `${f.duration(loss)} (target ${f.duration(rpo)})`],
    ['Recovery time target', f.duration(rto)],
    ['Recover to', 'AWS Singapore'],
    ['Expected cost', 'Estimated before any real recovery'],
  ]
  return (
    <dl className="flex flex-col text-[13px]">
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-4 border-t border-rule py-2 first:border-t-0">
          <dt className="text-muted">{k}</dt>
          <dd className="num m-0 text-right text-ink">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

function Progress({ state, point, onStop, onReset }: { state: RecoveryState | null; point: Backup | null; onStop: () => void; onReset: () => void }) {
  const { prefs } = usePrefs()
  if (!state) {
    return (
      <Loading label="recovery progress">
        <div className="panel h-[420px]" />
      </Loading>
    )
  }
  const ratio = state.simulatedElapsedSeconds / TOTAL_SIMULATED_SECONDS
  const current = state.steps.find((s) => s.status === 'running')
  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="panel p-5 sm:p-6" aria-labelledby="progress-title">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 id="progress-title" className="text-[18px] leading-6 font-semibold">
            {state.status === 'running' ? 'Recovering (simulated)' : state.status === 'succeeded' ? 'Simulated recovery finished' : 'Simulation stopped'}
          </h2>
          <span className="num text-[13px] text-muted">
            Simulated clock <span className="text-ink">{f.clock(state.simulatedElapsedSeconds)}</span> of {f.clock(TOTAL_SIMULATED_SECONDS)}
          </span>
        </div>
        <div
          className="mt-4 h-2 overflow-hidden rounded-full bg-raised"
          role="progressbar"
          aria-label="Simulated recovery progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(ratio * 100)}
        >
          <motion.div className="h-full origin-left rounded-full bg-accent" animate={{ scaleX: ratio }} initial={false} transition={{ duration: 0.15, ease: 'linear' }} />
        </div>
        <p className="sr-only" aria-live="polite">
          {state.status === 'running' ? `Now: ${current?.title ?? ''}` : state.status === 'succeeded' ? 'Simulated recovery finished.' : 'Simulation stopped.'}
        </p>

        <ol className="mt-5 flex flex-col">
          {state.steps.map((s) => (
            <li key={s.id} className="flex items-start gap-3 border-t border-rule py-3 first:border-t-0">
              <StepMark status={s.status} />
              <div className="min-w-0 flex-1">
                <div className={s.status === 'pending' ? 'text-muted' : 'text-ink'}>
                  {s.title}
                  <span className="sr-only">: {s.status === 'done' ? 'done' : s.status === 'running' ? 'in progress' : 'waiting'}</span>
                </div>
                {s.status === 'running' && <div className="text-[13px] text-muted">{s.detail}</div>}
              </div>
              <span className="num text-[13px] text-muted">{f.duration(Math.max(1, Math.round(s.simulatedSeconds / 60)))}</span>
            </li>
          ))}
        </ol>
        {state.status === 'running' && (
          <button type="button" className="btn btn-secondary mt-4" onClick={onStop}>
            Stop simulation
          </button>
        )}
      </section>

      <aside className="flex flex-col gap-4">
        {state.result ? (
          <motion.section
            className="panel p-5"
            aria-labelledby="result-title"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.22 }}
          >
            <div className="flex items-center justify-between gap-3">
              <h2 id="result-title" className="text-[18px] leading-6 font-semibold">
                Result
              </h2>
              <SimulatedTag />
            </div>
            <dl className="mt-4 flex flex-col gap-4">
              <ResultFigure label="Recovery time" value={f.duration(state.result.recoveryMinutes)} target={f.duration(state.result.rtoTargetMinutes)} ok={state.result.withinRto} />
              <ResultFigure label="Changes lost" value={f.duration(state.result.dataLossMinutes)} target={f.duration(state.result.rpoTargetMinutes)} ok={state.result.withinRpo} />
            </dl>
            {state.result.recordsValidated && (
              <div className="mt-4 rounded-lg bg-raised p-3 text-[13px]">
                <div className="text-muted">Records checked against the backup manifest</div>
                <div className="num mt-1 text-ink">
                  {f.count(state.result.recordsValidated.farmers)} members · {f.count(state.result.recordsValidated.inventoryItems)} items ·{' '}
                  {f.count(state.result.recordsValidated.transactions)} ledger entries
                </div>
              </div>
            )}
            <p className="mt-4 text-[12px] leading-[18px] text-muted">
              Simulation only: these timings are placeholders, not measurements. Real recovery times are recorded in the disaster-recovery
              drill.
            </p>
          </motion.section>
        ) : (
          <section className="panel p-5 text-[13px]" aria-label="Recovery point">
            <div className="text-muted">Restoring from</div>
            <div className="num mt-1 text-[15px] text-ink">{point ? f.dateTime(point.scheduledAt, prefs.timeZone) : '—'}</div>
            <p className="mt-3 text-muted">The result appears here when the last step finishes.</p>
          </section>
        )}
        {state.status !== 'running' && (
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn btn-primary" onClick={onReset}>
              Plan another simulation
            </button>
            <Link to="/activity" className="btn btn-secondary">
              View activity
            </Link>
          </div>
        )}
      </aside>
    </div>
  )
}

function StepMark({ status }: { status: 'pending' | 'running' | 'done' }) {
  if (status === 'done') {
    return (
      <motion.span
        className="mt-0.5 flex size-5 flex-none items-center justify-center rounded-full bg-accent text-white"
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.18 }}
      >
        <Check size={13} strokeWidth={3} aria-hidden="true" />
      </motion.span>
    )
  }
  if (status === 'running') {
    return (
      <span className="relative mt-0.5 flex size-5 flex-none items-center justify-center">
        <motion.span
          className="absolute inset-0 rounded-full bg-tint"
          animate={{ scale: [1, 1.25, 1] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
        />
        <span className="relative size-2.5 rounded-full bg-accent" />
      </span>
    )
  }
  return (
    <span className="mt-0.5 flex size-5 flex-none items-center justify-center">
      <Circle size={18} strokeWidth={1.5} className="text-control" aria-hidden="true" />
    </span>
  )
}

function ResultFigure({ label, value, target, ok }: { label: string; value: string; target: string; ok: boolean }) {
  return (
    <div>
      <dt className="text-[13px] text-muted">{label}</dt>
      <dd className="m-0 flex items-baseline gap-3">
        <span className="num text-[28px] leading-9 font-semibold text-ink">{value}</span>
        <span className={`text-[13px] ${ok ? 'text-accent-ink' : 'text-neg-ink'}`}>
          {ok ? 'Within' : 'Over'} the {target} target
        </span>
      </dd>
    </div>
  )
}
