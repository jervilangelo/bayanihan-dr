import type { Backup, RecoveryState, RecoveryStepState } from './types'

/**
 * A CLIENT-SIDE SIMULATION of the blueprint's recovery sequence (§10.1). It never calls AWS, Terraform
 * or any network service. Step durations are illustrative placeholders, not measurements; real
 * timings are recorded only in the Phase 7 disaster drill.
 */
export const RECOVERY_STEPS: ReadonlyArray<Omit<RecoveryStepState, 'status'>> = [
  { id: 'declare', title: 'Declare the incident', detail: 'Primary CMS marked unavailable; the recovery clock starts.', simulatedSeconds: 60 },
  { id: 'access', title: 'Confirm independent access', detail: 'Backup storage, AWS credentials, Terraform state and the runbook are reachable from this workstation.', simulatedSeconds: 120 },
  { id: 'approve', title: 'Approve the recovery plan', detail: 'The chosen recovery point and plan are approved; no other recovery may start.', simulatedSeconds: 60 },
  { id: 'provision', title: 'Provision recovery infrastructure', detail: 'Network, firewall rules and a small recovery server in Singapore (ap-southeast-1).', simulatedSeconds: 420 },
  { id: 'bootstrap', title: 'Prepare the recovery server', detail: 'Install Docker and fetch the cooperative system image.', simulatedSeconds: 240 },
  { id: 'download', title: 'Download and verify the backup', detail: 'The SHA-256 checksum must match the backup manifest.', simulatedSeconds: 60 },
  { id: 'restore', title: 'Restore the database', detail: 'Restore the PostgreSQL dump into a fresh database.', simulatedSeconds: 60 },
  { id: 'start', title: 'Start the cooperative system', detail: 'Start the CMS and wait for it to accept connections.', simulatedSeconds: 60 },
  { id: 'health', title: 'Run health checks', detail: 'The readiness check must report the expected schema revision.', simulatedSeconds: 60 },
  { id: 'validate', title: 'Validate business records', detail: 'Member, inventory and ledger counts must match the backup manifest.', simulatedSeconds: 60 },
  { id: 'report', title: 'Record the result', detail: 'Write recovery time, data-loss window and evidence to the report.', simulatedSeconds: 60 },
]
// Whole minutes only, so the per-step minutes shown on screen add up exactly to the total shown.

export const TOTAL_SIMULATED_SECONDS = RECOVERY_STEPS.reduce((n, s) => n + s.simulatedSeconds, 0)
export const DEFAULT_RTO_MINUTES = 30
export const DEFAULT_RPO_MINUTES = 60

export interface SimulatedJob {
  id: string
  backup: Backup
  declaredAt: Date
  startedAtRealMs: number
  /** Simulated seconds per real second. */
  speed: number
  cancelledAtRealMs: number | null
  rtoTargetMinutes: number
  rpoTargetMinutes: number
}

let sequence = 0

export function createSimulatedJob(
  backup: Backup,
  declaredAt: Date,
  startedAtRealMs: number,
  speed: number,
  targets = { rtoMinutes: DEFAULT_RTO_MINUTES, rpoMinutes: DEFAULT_RPO_MINUTES },
): SimulatedJob {
  if (backup.status !== 'verified' || backup.restoreTest !== 'passed') {
    throw new Error('Only a verified recovery point can be restored')
  }
  sequence += 1
  return {
    id: `sim-${declaredAt.toISOString().slice(0, 10).replaceAll('-', '')}-${String(sequence).padStart(3, '0')}`,
    backup,
    declaredAt,
    startedAtRealMs,
    speed,
    cancelledAtRealMs: null,
    rtoTargetMinutes: targets.rtoMinutes,
    rpoTargetMinutes: targets.rpoMinutes,
  }
}

/** Pure function of the job and the real clock, so the state machine is trivially testable. */
export function jobStateAt(job: SimulatedJob, nowRealMs: number): RecoveryState {
  const effectiveNow = job.cancelledAtRealMs === null ? nowRealMs : Math.min(nowRealMs, job.cancelledAtRealMs)
  const raw = (Math.max(0, effectiveNow - job.startedAtRealMs) / 1000) * job.speed
  const elapsed = Math.min(TOTAL_SIMULATED_SECONDS, Math.round(raw))

  let cursor = 0
  const steps: RecoveryStepState[] = RECOVERY_STEPS.map((s) => {
    const start = cursor
    cursor += s.simulatedSeconds
    const status = elapsed >= cursor ? 'done' : elapsed >= start ? 'running' : 'pending'
    return { ...s, status }
  })

  const finished = elapsed >= TOTAL_SIMULATED_SECONDS
  const cancelled = job.cancelledAtRealMs !== null && !finished
  const recoveryMinutes = TOTAL_SIMULATED_SECONDS / 60
  const dataLossMinutes = Math.floor((job.declaredAt.getTime() - Date.parse(job.backup.scheduledAt)) / 60_000)

  return {
    jobId: job.id,
    backupId: job.backup.id,
    status: cancelled ? 'cancelled' : finished ? 'succeeded' : 'running',
    declaredAt: job.declaredAt.toISOString(),
    simulatedElapsedSeconds: elapsed,
    steps: cancelled ? steps.map((s) => (s.status === 'running' ? { ...s, status: 'pending' } : s)) : steps,
    result:
      finished && !cancelled
        ? {
            simulated: true,
            recoveryMinutes,
            dataLossMinutes,
            rtoTargetMinutes: job.rtoTargetMinutes,
            rpoTargetMinutes: job.rpoTargetMinutes,
            withinRto: recoveryMinutes <= job.rtoTargetMinutes,
            withinRpo: dataLossMinutes <= job.rpoTargetMinutes,
            recordsValidated: job.backup.records,
          }
        : null,
  }
}
