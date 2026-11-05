/**
 * Client for the local recovery job runner (backend/bdr_runner), used only in local operations mode.
 *
 * Requests go through the Vite dev server's proxy, so they are same-origin. The administrator token is kept in
 * sessionStorage (it is cleared when the tab closes) and is sent as a bearer token, never in a URL or cookie.
 * The public GitHub Pages build never includes this module.
 */

export type JobStatus = 'preparing' | 'awaiting-approval' | 'applying' | 'restoring' | 'succeeded' | 'failed' | 'cancelled'
export type StepStatus = 'pending' | 'running' | 'ok' | 'failed' | 'skipped'

export interface JobStep {
  id: string
  title: string
  status: StepStatus
  started_at: string | null
  finished_at: string | null
  detail: string
}

export interface PlanSummary {
  counts: { create: number; update: number; delete: number; replace: number }
  resources: { address: string; type: string; action: string }[]
  hourly_cost_usd: number
}

export interface RecoveryResult {
  simulated: false
  declared_at: string
  recovered_at: string
  rto_seconds: number
  rpo_seconds: number
  rto_target_seconds: number
  rpo_target_seconds: number
  within_rto: boolean
  within_rpo: boolean
  approval_wait_seconds: number | null
  provision_seconds: number | null
  host_seconds: number | null
  restore_ms: number | null
  records: { restored: Record<string, number> | null; expected: Record<string, number> | null }
  recovery_point: OffsitePoint
}

export interface RunnerJob {
  id: string
  type: 'recovery-drill' | 'teardown'
  status: JobStatus
  created_at: string
  backup_id: string | null
  declared_at: string | null
  approved_at: string | null
  finished_at: string | null
  app_git_ref: string | null
  plan: PlanSummary | null
  steps: JobStep[]
  result: (Partial<RecoveryResult> & { recovery_point?: OffsitePoint }) | null
  error: string | null
}

export interface OffsitePoint {
  id: string
  scheduledAt: string
  completedAt: string | null
  sizeBytes: number
  sha256: string
  schemaRevision: string
  records: Record<string, number>
}

export interface AuditEntry {
  at: string
  actor: string
  action: string
  job_id: string | null
  detail: string
}

export class RunnerError extends Error {
  readonly status: number
  readonly code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
    this.name = 'RunnerError'
  }
}

export const ACTIVE_STATUSES: JobStatus[] = ['preparing', 'awaiting-approval', 'applying', 'restoring']
const TOKEN_KEY = 'bayanihandr.runnerToken'

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token.trim())
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    /* storage unavailable: the token lasts only for this page load */
  }
}

export function createRunnerClient(base: string, fetchImpl: typeof fetch = (...a) => fetch(...a), token: () => string | null = getToken) {
  async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
    const t = token()
    if (!t) throw new RunnerError(401, 'no-token', 'Enter the administrator token to use the job runner.')
    let res: Response
    try {
      res = await fetchImpl(`${base}${path}`, {
        ...init,
        cache: 'no-store',
        headers: { Authorization: `Bearer ${t}`, ...(init.body ? { 'Content-Type': 'application/json' } : {}) },
      })
    } catch {
      throw new RunnerError(0, 'unreachable', 'The job runner is not running. Start it with: python -m bdr_runner')
    }
    if (res.status === 502 || res.status === 504) {
      throw new RunnerError(0, 'unreachable', 'The job runner is not running. Start it with: python -m bdr_runner')
    }
    const body = await res.json().catch(() => ({}))
    if (!res.ok) {
      const detail = typeof body.detail === 'string' ? body.detail : `Request failed (HTTP ${res.status})`
      throw new RunnerError(res.status, body.code ?? (res.status === 401 ? 'unauthorized' : 'error'), detail)
    }
    return body as T
  }

  return {
    session: () => call<{ authenticated: true; identity: string }>('/api/session'),
    recoveryPoints: () => call<OffsitePoint[]>('/api/recovery-points'),
    jobs: () => call<RunnerJob[]>('/api/jobs'),
    job: (id: string) => call<RunnerJob>(`/api/jobs/${encodeURIComponent(id)}`),
    startDrill: (backupId: string) => call<RunnerJob>('/api/jobs', { method: 'POST', body: JSON.stringify({ type: 'recovery-drill', backup_id: backupId }) }),
    startTeardown: () => call<RunnerJob>('/api/jobs', { method: 'POST', body: JSON.stringify({ type: 'teardown' }) }),
    approve: (id: string, confirm: string) =>
      call<RunnerJob>(`/api/jobs/${encodeURIComponent(id)}/approve`, { method: 'POST', body: JSON.stringify({ confirm_job_id: confirm }) }),
    cancel: (id: string) => call<RunnerJob>(`/api/jobs/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
    audit: () => call<AuditEntry[]>('/api/audit'),
  }
}

export type RunnerClient = ReturnType<typeof createRunnerClient>
