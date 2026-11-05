import { readinessOf } from './readiness'
import {
  ProviderError,
  type ActivityEvent,
  type Backup,
  type DashboardProvider,
  type Overview,
  type PrimaryServer,
  type RecoveryTargets,
  type Settings,
} from './types'

/**
 * Local operations mode, read-only (Phase 3).
 *
 * Reads the status.json that the backup engine writes (backend/bdr_engine/status.py, schema v1). It can
 * only show what the engine reported; it cannot start backups or recoveries. Real recovery orchestration,
 * with authentication, arrives in Phase 6. This provider is excluded from the public GitHub Pages build.
 */

export interface EngineStatus {
  schemaVersion: 1
  generatedAt: string
  mode: 'operational'
  primary: PrimaryServer
  targets: RecoveryTargets
  schedule: { intervalMinutes: number; description: string }
  retention: { description: string }
  restoreTest: string
  database: string
  backups: Backup[]
  activity: ActivityEvent[]
}

export interface LocalStatusProviderOptions {
  url: string
  fetchImpl?: typeof fetch
  now?: () => Date
}

export function parseEngineStatus(raw: unknown): EngineStatus {
  const s = raw as Partial<EngineStatus> | null
  if (!s || typeof s !== 'object' || s.schemaVersion !== 1 || !Array.isArray(s.backups) || !Array.isArray(s.activity) || !s.primary || !s.targets) {
    throw new ProviderError('status-unavailable', 'The backup engine status file is not in the expected format (schema v1).')
  }
  return s as EngineStatus
}

export function createLocalStatusProvider(options: LocalStatusProviderOptions): DashboardProvider {
  const fetchImpl = options.fetchImpl ?? ((...args: Parameters<typeof fetch>) => fetch(...args))
  const now = options.now ?? (() => new Date())

  async function load(): Promise<EngineStatus> {
    let res: Response
    try {
      res = await fetchImpl(options.url, { cache: 'no-store' })
    } catch {
      throw new ProviderError('status-unavailable', 'Could not reach the local status file.')
    }
    if (!res.ok) {
      throw new ProviderError(
        'status-unavailable',
        res.status === 404
          ? 'No backup status yet. Run the backup engine once to create it.'
          : `The status file could not be read (HTTP ${res.status}).`,
      )
    }
    return parseEngineStatus(await res.json())
  }

  const unavailable = () =>
    new ProviderError('recovery-unavailable', 'Recovery jobs are not available in local mode yet. They arrive in Phase 6.')

  return {
    mode: 'operational',

    async getOverview(): Promise<Overview> {
      const s = await load()
      return {
        generatedAt: now().toISOString(),
        primary: s.primary,
        readiness: readinessOf(s.backups, now(), s.targets.rpoMinutes),
        targets: s.targets,
      }
    },

    async listBackups() {
      return (await load()).backups
    },

    async listActivity() {
      return (await load()).activity
    },

    async getSettings(): Promise<Settings> {
      const s = await load()
      return {
        mode: 'operational',
        environment: 'Local operations (job runner, Phase 6)',
        region: 'ap-southeast-1 (Singapore)',
        timeZone: 'Asia/Manila (PHT, UTC+8)',
        targets: s.targets,
        schedule: { expression: `every ${s.schedule.intervalMinutes} min`, description: s.schedule.description },
        retention: { description: s.retention.description, decided: true },
        restoreTest: s.restoreTest,
        cms: { version: '0.1.0', schemaRevision: s.primary.schemaRevision, database: `PostgreSQL database "${s.database}"` },
      }
    },

    async startRecovery() {
      throw unavailable()
    },
    async getRecoveryState() {
      throw unavailable()
    },
    async cancelRecovery() {
      throw unavailable()
    },
    async activeRecovery() {
      return null
    },
  }
}
