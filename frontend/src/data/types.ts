/**
 * Data contracts shared by every provider.
 *
 * The dashboard pages only talk to a `DashboardProvider`, so the static demo provider (GitHub Pages)
 * and the future authenticated operations provider (Phase 6) are interchangeable (blueprint §6.3).
 */

/** `pending`: the backup exists but has not passed verification yet, so it is never a recovery point. */
export type BackupStatus = 'verified' | 'pending' | 'failed' | 'missed'

export interface RecordCounts {
  farmers: number
  inventoryItems: number
  transactions: number
}

export interface Backup {
  id: string
  /** When the hourly schedule should have produced this backup (UTC ISO). */
  scheduledAt: string
  completedAt: string | null
  status: BackupStatus
  sizeBytes: number | null
  sha256: string | null
  checksum: 'match' | 'mismatch' | 'not-run'
  restoreTest: 'passed' | 'failed' | 'not-run'
  offsite: 'stored' | 'rejected' | 'not-stored'
  records?: RecordCounts
  failureReason?: string
  schemaRevision: string
  /** Operational mode only: how the backup was started and what verification checked. */
  trigger?: 'scheduled' | 'manual' | 'unknown'
  verifiedAt?: string | null
  restoreSeconds?: number | null
  checks?: VerificationCheck[]
}

export interface VerificationCheck {
  name: string
  ok: boolean
  detail: string
}

export type ReadinessState = 'protected' | 'outside-target' | 'no-recovery-point'

export interface Readiness {
  state: ReadinessState
  latestVerified: Backup | null
  recoveryPointAgeMinutes: number | null
  rpoTargetMinutes: number
  counts: Record<BackupStatus, number>
}

export interface PrimaryServer {
  name: string
  location: string
  status: 'online' | 'unreachable'
  checkedAt: string
  schemaRevision: string
}

export interface Overview {
  generatedAt: string
  primary: PrimaryServer
  readiness: Readiness
  targets: RecoveryTargets
}

export interface RecoveryTargets {
  rtoMinutes: number
  rpoMinutes: number
}

export type ActivityCategory = 'backup' | 'recovery' | 'infrastructure' | 'audit'
export type Severity = 'info' | 'warning' | 'error'

export interface ActivityEvent {
  id: string
  at: string
  category: ActivityCategory
  severity: Severity
  title: string
  detail: string
  actor: string
  backupId?: string
  jobId?: string
  simulated: boolean
}

export interface Settings {
  mode: 'demo' | 'operational'
  environment: string
  region: string
  timeZone: string
  targets: RecoveryTargets
  schedule: { expression: string; description: string }
  retention: { description: string; decided: boolean }
  restoreTest: string
  cms: { version: string; schemaRevision: string; database: string }
}

export type StepStatus = 'pending' | 'running' | 'done'

export interface RecoveryStepState {
  id: string
  title: string
  detail: string
  simulatedSeconds: number
  status: StepStatus
}

export interface RecoveryResult {
  simulated: true
  recoveryMinutes: number
  dataLossMinutes: number
  rtoTargetMinutes: number
  rpoTargetMinutes: number
  withinRto: boolean
  withinRpo: boolean
  recordsValidated: RecordCounts | undefined
}

export interface RecoveryState {
  jobId: string
  backupId: string
  status: 'running' | 'succeeded' | 'cancelled'
  declaredAt: string
  simulatedElapsedSeconds: number
  steps: RecoveryStepState[]
  result: RecoveryResult | null
}

export interface RecoveryJobRef {
  id: string
  backupId: string
}

export type ProviderErrorCode =
  | 'job-already-running'
  | 'unknown-recovery-point'
  | 'recovery-point-not-verified'
  | 'unknown-job'
  | 'recovery-unavailable'
  | 'status-unavailable'

export class ProviderError extends Error {
  readonly code: ProviderErrorCode
  constructor(code: ProviderErrorCode, message: string) {
    super(message)
    this.code = code
    this.name = 'ProviderError'
  }
}

export interface DashboardProvider {
  readonly mode: 'demo' | 'operational'
  getOverview(): Promise<Overview>
  listBackups(): Promise<Backup[]>
  listActivity(): Promise<ActivityEvent[]>
  getSettings(): Promise<Settings>
  startRecovery(backupId: string): Promise<RecoveryJobRef>
  getRecoveryState(jobId: string): Promise<RecoveryState>
  cancelRecovery(jobId: string): Promise<void>
  /** The job currently running, if any, so a reload of the Recovery page can resume watching it. */
  activeRecovery(): Promise<RecoveryJobRef | null>
}
