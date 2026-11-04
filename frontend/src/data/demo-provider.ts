import { DEMO_NOW, buildDemoDataset } from './demo-dataset'
import { readinessOf } from './readiness'
import { DEFAULT_RPO_MINUTES, DEFAULT_RTO_MINUTES, createSimulatedJob, jobStateAt, type SimulatedJob } from './simulation'
import {
  ProviderError,
  type ActivityEvent,
  type DashboardProvider,
  type Overview,
  type Settings,
} from './types'

export interface DemoProviderOptions {
  /** Real clock in ms (injectable for tests). */
  now?: () => number
  /** Artificial latency so loading states are visible; 0 in tests. */
  latencyMs?: number
  /** Simulated seconds per real second of playback. */
  speed?: number
}

const TARGETS = { rtoMinutes: DEFAULT_RTO_MINUTES, rpoMinutes: DEFAULT_RPO_MINUTES }

/**
 * Static, in-browser provider for the public demo. It holds no credentials and makes no network
 * requests; "recoveries" are simulations played back on the visitor's screen.
 */
export function createDemoProvider(options: DemoProviderOptions = {}): DashboardProvider {
  const now = options.now ?? (() => performance.now())
  const latency = options.latencyMs ?? 250
  const speed = options.speed ?? 100
  const { backups, activity: seededActivity } = buildDemoDataset()
  const recoveryActivity: ActivityEvent[] = []
  const jobs = new Map<string, SimulatedJob>()
  const finishedLogged = new Set<string>()

  const wait = <T,>(value: T): Promise<T> =>
    latency > 0 ? new Promise((r) => setTimeout(() => r(value), latency)) : Promise.resolve(value)

  function logFinished() {
    for (const job of jobs.values()) {
      const state = jobStateAt(job, now())
      if (state.status === 'running' || finishedLogged.has(job.id)) continue
      finishedLogged.add(job.id)
      recoveryActivity.push({
        id: `ev-${job.id}-end`,
        at: new Date(DEMO_NOW.getTime() + state.simulatedElapsedSeconds * 1000).toISOString(),
        category: 'recovery',
        severity: state.status === 'succeeded' ? 'info' : 'warning',
        title: state.status === 'succeeded' ? 'Simulated recovery finished' : 'Simulated recovery stopped',
        detail:
          state.status === 'succeeded'
            ? `Simulation only: no AWS resources were created. Recovery point ${job.backup.id}.`
            : 'The visitor stopped the simulation before it finished.',
        actor: 'Demo visitor',
        jobId: job.id,
        backupId: job.backup.id,
        simulated: true,
      })
    }
  }

  function running(): SimulatedJob | undefined {
    return [...jobs.values()].find((j) => jobStateAt(j, now()).status === 'running')
  }

  return {
    mode: 'demo',

    async getOverview(): Promise<Overview> {
      return wait({
        generatedAt: DEMO_NOW.toISOString(),
        primary: {
          name: 'BFC office server',
          location: 'Naga City office',
          status: 'online',
          checkedAt: new Date(DEMO_NOW.getTime() - 60_000).toISOString(),
          schemaRevision: '0001',
        },
        readiness: readinessOf(backups, DEMO_NOW, TARGETS.rpoMinutes),
        targets: TARGETS,
      })
    },

    async listBackups() {
      return wait(backups)
    },

    async listActivity() {
      logFinished()
      return wait([...recoveryActivity, ...seededActivity].sort((a, b) => Date.parse(b.at) - Date.parse(a.at)))
    },

    async getSettings(): Promise<Settings> {
      return wait({
        mode: 'demo',
        environment: 'Public demo (simulated data)',
        region: 'ap-southeast-1 (Singapore)',
        timeZone: 'Asia/Manila (PHT, UTC+8)',
        targets: TARGETS,
        schedule: { expression: '5 * * * *', description: 'Every hour at 5 minutes past' },
        retention: { description: '72 hourly backups (proposal; confirmed in Phase 3)', decided: false },
        restoreTest: 'Every backup is test-restored into a disposable database before it counts as a recovery point.',
        cms: { version: '0.1.0', schemaRevision: '0001', database: 'PostgreSQL 16' },
      })
    },

    async startRecovery(backupId) {
      if (running()) throw new ProviderError('job-already-running', 'A recovery is already running. Wait for it to finish or stop it first.')
      const backup = backups.find((b) => b.id === backupId)
      if (!backup) throw new ProviderError('unknown-recovery-point', `No backup ${backupId}`)
      if (backup.status !== 'verified') throw new ProviderError('recovery-point-not-verified', 'Only verified recovery points can be restored.')
      const job = createSimulatedJob(backup, DEMO_NOW, now(), speed, TARGETS)
      jobs.set(job.id, job)
      recoveryActivity.push({
        id: `ev-${job.id}-start`,
        at: DEMO_NOW.toISOString(),
        category: 'recovery',
        severity: 'info',
        title: 'Simulated recovery approved',
        detail: `Recovery point ${backup.id} selected and approved in demo mode.`,
        actor: 'Demo visitor',
        jobId: job.id,
        backupId: backup.id,
        simulated: true,
      })
      return { id: job.id, backupId: backup.id }
    },

    async getRecoveryState(jobId) {
      const job = jobs.get(jobId)
      if (!job) throw new ProviderError('unknown-job', `No recovery ${jobId}`)
      logFinished()
      return jobStateAt(job, now())
    },

    async cancelRecovery(jobId) {
      const job = jobs.get(jobId)
      if (!job) throw new ProviderError('unknown-job', `No recovery ${jobId}`)
      if (job.cancelledAtRealMs === null) job.cancelledAtRealMs = now()
      logFinished()
    },

    async activeRecovery() {
      const job = running()
      return job ? { id: job.id, backupId: job.backup.id } : null
    },
  }
}
