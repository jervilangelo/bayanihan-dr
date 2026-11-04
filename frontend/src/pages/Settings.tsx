import type { ReactNode } from 'react'
import { BlockError, Loading, PageHeader, Skeleton } from '../components/ui'
import type { DashboardProvider } from '../data/types'
import { usePrefs, useResource } from '../lib/context'
import * as f from '../lib/format'

const loadSettings = (p: DashboardProvider) => p.getSettings()

export function SettingsPage() {
  const res = useResource(loadSettings)
  const { prefs, setPrefs } = usePrefs()
  const s = res.data
  const demo = s?.mode === 'demo'

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Settings" subline="Recovery targets, the backup schedule and the environment BayanihanDR recovers into." />

      {res.error && <BlockError what="settings" onRetry={res.retry} />}
      {res.loading && (
        <Loading label="settings">
          <div className="panel p-6">
            <Skeleton w={200} />
            <Skeleton w="50%" className="mt-3" />
          </div>
        </Loading>
      )}

      {s && (
        <div className="flex flex-col">
          {demo && (
            <p className="mb-2 rounded-lg border border-warn-border bg-warn-bg px-4 py-3 text-[13px] leading-5 text-warn-ink">
              These values are read-only in the public demo. Changing targets, schedules or credentials is only possible in local
              operations mode, by a signed-in administrator.
            </p>
          )}

          <Row title="Recovery targets" help="What the cooperative has agreed to aim for. They are goals, not results; drills measure the real figures.">
            <KV k="Recovery time objective (RTO)" v={`${s.targets.rtoMinutes} min`} hint="From declaring the incident to a working system" />
            <KV k="Recovery point objective (RPO)" v={f.duration(s.targets.rpoMinutes)} hint="The most recent changes the cooperative can afford to lose" />
          </Row>

          <Row title="Backups" help="How often the database is copied and how each copy is proven usable.">
            <KV k="Schedule" v={s.schedule.description} hint={<span className="font-mono">{s.schedule.expression}</span>} />
            <KV k="Verification" v="Checksum and test restore" hint={s.restoreTest} />
            <KV k="Retention" v={s.retention.description} hint={s.retention.decided ? undefined : 'Open decision OD-4 in the blueprint'} />
          </Row>

          <Row title="Environment" help="Where things run. The recovery region is fixed by the project blueprint.">
            <KV k="Mode" v={s.environment} />
            <KV k="Recovery region" v={s.region} />
            <KV k="Time zone" v={s.timeZone} />
            <KV k="Cooperative system" v={`Version ${s.cms.version}, schema ${s.cms.schemaRevision}`} hint={s.cms.database} />
          </Row>

          <Row title="Display preferences" help="Saved in this browser only.">
            <fieldset className="py-2">
              <legend className="text-[14px] font-medium text-ink">Show times in</legend>
              <div className="mt-2 flex flex-wrap gap-2">
                {(['pht', 'utc'] as const).map((tz) => (
                  <Choice key={tz} name="tz" checked={prefs.timeZone === tz} onChange={() => setPrefs({ timeZone: tz })}>
                    {tz === 'pht' ? 'Philippine time (PHT)' : 'UTC'}
                  </Choice>
                ))}
              </div>
            </fieldset>
            <fieldset className="border-t border-rule py-3">
              <legend className="pt-3 text-[14px] font-medium text-ink">Animation</legend>
              <div className="mt-2 flex flex-wrap gap-2">
                <Choice name="motion" checked={prefs.motion === 'system'} onChange={() => setPrefs({ motion: 'system' })}>
                  Follow my device setting
                </Choice>
                <Choice name="motion" checked={prefs.motion === 'reduce'} onChange={() => setPrefs({ motion: 'reduce' })}>
                  Reduce motion
                </Choice>
              </div>
            </fieldset>
          </Row>

          {!demo && (
            <Row title="Credentials" help="Managed in local operations mode.">
              <KV k="Status" v="Configured on the recovery workstation" />
            </Row>
          )}
        </div>
      )}
    </div>
  )
}

function Row({ title, help, children }: { title: string; help: string; children: ReactNode }) {
  return (
    <section className="grid grid-cols-1 gap-3 border-t border-border py-6 first:border-t-0 md:grid-cols-[minmax(0,320px)_minmax(0,1fr)] md:gap-10">
      <div>
        <h2 className="text-[16px] leading-6 font-semibold text-ink">{title}</h2>
        <p className="mt-1 text-[13px] leading-5 text-muted">{help}</p>
      </div>
      <div className="panel px-5 py-2">{children}</div>
    </section>
  )
}

function KV({ k, v, hint }: { k: string; v: ReactNode; hint?: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 border-t border-rule py-3 first:border-t-0 sm:flex-row sm:items-baseline sm:justify-between sm:gap-6">
      <div className="text-ink">{k}</div>
      <div className="sm:text-right">
        <div className="num font-medium text-ink">{v}</div>
        {hint && <div className="text-[12px] leading-[18px] text-muted">{hint}</div>}
      </div>
    </div>
  )
}

function Choice({ name, checked, onChange, children }: { name: string; checked: boolean; onChange: () => void; children: ReactNode }) {
  return (
    <label
      className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border px-3 text-[14px] transition-colors duration-150 ${
        checked ? 'border-accent bg-tint-soft text-accent-ink' : 'border-control text-ink hover:border-muted'
      }`}
    >
      <input type="radio" name={name} className="size-4 accent-[var(--color-accent)]" checked={checked} onChange={onChange} />
      {children}
    </label>
  )
}
